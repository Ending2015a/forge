# --- built in ---
import os
import sys
import time
import types
import inspect
import logging
import traceback
import functools

from collections import OrderedDict
# --- 3rd party ---


# --- my module ---


__all__ = [
    'dictionarize',
    'ParameterPack',
    'argshandler',
]

def _retrieve_outer_frame(outer=2):
    frame = inspect.currentframe()
    for i in range(outer):
        if frame is None:
            break
        frame = frame.f_back

    if frame is not None:

        # frame info
        frame = {
            'filename': frame.f_code.co_filename,
            'lineno': frame.f_lineno
        }

    return frame

def _forge_func(name, source, kwargs, namespace):

    local_namespace = locals()
    local_namespace.update(namespace)

    _source = source.format(**kwargs)


    exec(_source, local_namespace)

    func = locals()[name]
    func._forge_source = _source

    return func



_dictionarize_scode_template = '''\
from builtins import dict as _dict
from builtins import property as _property
from operator import itemgetter as _itemgetter


class {class_name}(dict):
    \'\'\'Dictionarized {func_name}{signature}\'\'\'

    __slots__ = ()

    def __new__(_cls, {param_list}):
        \'\'\'
        Instantiate new object
        \'\'\'
        return _dict.__new__(_cls)

    def __init__(self, {param_list}):
        super({class_name}, self).__init__({{ {kwargs_list} }})
        {append_kwargs_to_fields}

    def __call__(self, {input_param_list} **_) {return_annotation}:
        \'\'\'
        Call function
        \'\'\'

        _ = {{**self, **_}}

        {pop_args} # pop args from _

        return {func_name}({func_param_list}**_)

    def __repr__(self):
        return '{class_name}({{}})'.format(', '.join(
                    '{{}}={{!r}}'.format(f, self[f]) for f in self._fields) )

    _input_fields = [{input_fields}]
    _fields = [{param_fields}]

    # === properties ===

{property_list}
'''

_property_scode_template = '''\
    {property_name} = _property(_itemgetter({property_name!r}), doc='Alias for property {property_name}')
'''


def dictionarize(function, name: str=None, inputs: set=set()):
    '''
    dictionarize

    Args:
        function: a function
        name: (str or None) the name of generated class. If set to None, the following operations will be used:
            function.__name__.replace('_', ' ').title().replace(' ', '')
        inputs: (a list/tuple/set of int or str) the names or position indices of the arguments that must 
            be passed at calling __call__
    '''
    # get function signature
    sign = inspect.signature(function)

    # check if inputs is an array
    if inputs is None:
        inputs = set()
    elif not isinstance(inputs, (tuple, list, set)):
        inputs = set(inputs)


    # check if wach element in inputs is str
    for i in inputs:
        assert isinstance(i, str),'inputs must be a list of `str` object, {} were given'.format(type(i))

    _input_params = set(inputs)

    # prepare
    func_name = function.__name__
    class_name = name if name is not None else func_name.replace('_', ' ').title().replace(' ', '')
    signature = str(sign)
    return_annotation = ''
    args_name = None
    kwargs_name = None
    param_list = []
    kwargs_list = []
    input_param_list = []
    input_fields = []
    param_fields = []
    property_list = []
    func_param_list = []
    #unpack_args = ''
    pop_args = ''
    return_annotation = ''
    append_kwargs_to_fields = ''

    # handle return annotation
    if sign.return_annotation != inspect.Signature.empty:
        return_annotation = '-> {!r}'.format(sign.return_annotation)
    
    # handle parameters
    for idx, param in enumerate(sign.parameters.values()):

        # input
        if (param.name in _input_params) or (idx in _input_params):

            # do not accept variable-length keyword arguments as input arguments
            if param.kind == param.VAR_KEYWORD:
                continue

            input_fields.append('{!r}'.format(param.name))
            input_param_list.append(str(param))

            if param.kind == param.KEYWORD_ONLY:
                func_param_list.append('{0}={0}'.format(param.name))
            elif param.kind == param.VAR_POSITIONAL:
                func_param_list.append(str(param))
            else:
                func_param_list.append(param.name)

        # not input
        else:
            # __init__ signature
            param_list.append(str(param))
    
            # variable-length positional argument
            if param.kind == param.VAR_POSITIONAL:
                param_fields.append('{!r}'.format(param.name))
                # kw
                kwargs_list.append('{0!r}: {0}'.format(param.name))
                args_name = param.name

                pop_args = '{0} = _.pop({0!r}, [])'.format(args_name)

                property_list.append(_property_scode_template.format(property_name=param.name))

                func_param_list.append(str(param))

            # variable-length keyword argument
            elif param.kind == param.VAR_KEYWORD:
                # unpack kwargs
                kwargs_list.append(str(param))
                kwargs_name = param.name
                append_kwargs_to_fields = 'self._fields.extend(list({}.keys()))'.format(param.name)

            # others
            else:
                param_fields.append('{!r}'.format(param.name))
                # kw
                kwargs_list.append('{0!r}: {0}'.format(param.name))
                property_list.append(_property_scode_template.format(property_name=param.name))

                if (param.kind == param.POSITIONAL_ONLY or
                      (param.kind == param.POSITIONAL_OR_KEYWORD and param.default is param.empty)):
                    func_param_list.append('_.pop({!r})'.format(param.name))



    if len(input_param_list) > 0:
        # append empty str to add an extra ',' to the tail of ', '.join(input_param_list) 
        input_param_list.append('')

    if len(func_param_list) > 0:
        # append empty str to add an extra ',' to the tail of ', '.join(input_param_list) 
        func_param_list.append('')
        
    source_vars = {
        'func_name': func_name,
        'class_name': class_name,
        'signature': signature,
        'return_annotation': return_annotation,
        'param_list': ', '.join(param_list),
        'kwargs_list': ', '.join(kwargs_list),
        'input_param_list': ', '.join(input_param_list),
        'input_fields': ', '.join(input_fields),
        'param_fields': ', '.join(param_fields),
        'property_list': ''.join(property_list),
        'func_param_list': ', '.join(func_param_list),
        'pop_args': pop_args,
        'return_annotation': return_annotation,
        'append_kwargs_to_fields': append_kwargs_to_fields,
        }

    namespace = {func_name: function}

    forged_class = _forge_func(class_name, 
                               _dictionarize_scode_template,
                               source_vars,
                               namespace)

    return forged_class
    

def set_parameterpack_warning_level(b):
    '''
    set warning level

    ERROR: raise exception
    WARNING: print warning info
    WARN-V: print warning info and stack traces
    IGNORE: ignore any exceptions

    Args:
        b: (str or int)
    '''
    mapping = {'ERROR': 0, 'WARNING': 1, 'WARN-V': 2, 'IGNORE': 3,
               'error': 0, 'warning': 1, 'warn-v': 2, 'ignore': 3,
               'e': 0, 'w': 1, 'wv': 2, 'i': 3}

    if isinstance(b, str):
        assert b in mapping.keys()
        ParameterPack._warning_level = mapping[b]
    else:
        assert isinstance(b, int)
        ParameterPack._warning_level = b

class ParameterPack(OrderedDict):
    '''
    ParameterPack

    It's a kind of named tuple, but implemented using OrderedDict.
    '''

    _warning_level = 0

    # === private member ===
    _parameterpack_scode_template = '''\
def {name}{signature}:
    arg_list = [{kwpair_list!s}]
{unpack_kwargs_code}
    # create OrderedDict, cls = ParameterPack
    package = cls(arg_list)
{setattr_package_code}
    return package
'''

    _unpack_kwargs_scode_template = '''\
    for k, v in {kwargs_name}.items():
        arg_list.append((k, v))
'''

    _setattr_package_scode_template = '''\
    setattr({target}, {property!r}, package)
'''

    def __init__(self, *args, **kwargs):
        super(ParameterPack, self).__init__(*args, **kwargs)
        object.__setattr__(self, '__dict__', self)

    def __iter__(self):
        yield from self.values()

    def __getitem__(self, key):
        if self.__class__._warning_level == 0:
            return super(ParameterPack, self).__getitem__(key)
        elif self.__class__._warning_level == 1:
            try:
                return super(ParameterPack, self).__getitem__(key)
            except KeyError:
                # print warning message and return None
                frame = _retrieve_outer_frame()
                print('WARNING:forge:From {}:{}: unexisted key (from forge.ParameterPack.__getitem__): {}. '
                                    'For more traceback info, please set_parameterpack_warning_level(2)'.format(
                                                                frame['filename'], frame['lineno'], key))
                return None
        elif self.__class__._warning_level == 2:
            try:
                return super(ParameterPack, self).__getitem__(key)
            except KeyError:
                # print warning message, stack traces and return None
                frame = _retrieve_outer_frame()
                print('WARNING:forge:From {}:{}: unexisted key (from forge.ParameterPack.__getitem__): {}'.format(
                                                                frame['filename'], frame['lineno'], key))
                traceback.print_stack(f=inspect.currentframe().f_back)
                return None
        else:
            return super(ParameterPack, self).get(key, None)

    def __getattr__(self, name):
        if self.__class__._warning_level == 0:
            return object.__getattribute__(self, name)
        elif self.__class__._warning_level == 1:
            try:
                return object.__getattribute__(self, name)
            except AttributeError:
                # print warning message and return None
                frame = _retrieve_outer_frame()
                print('WARNING:forge:From {}:{}: unexisted name (from forge.ParameterPack.__getattr__): {}. '
                                    'For more traceback info, please set_parameterpack_warning_level(2)'.format(
                                                                frame['filename'], frame['lineno'], name))
                return None
        elif self.__class__._warning_level == 2:
            try:
                return object.__getattribute__(self, name)
            except AttributeError:
                # print warning message, stack traces and return None
                print('WARNING:forge:From {}:{}: unexisted name (from forge.ParameterPack.__getattr__): {}.'.format(
                                                                frame['filename'], frame['lineno'], name))
                traceback.print_stack(f=inspect.currentframe().f_back)
                return None
        else:
            return super(ParameterPack, self).get(name, None)

    def __setattr__(self, name, value):
        self.__setitem__(name, value)

    def __delattr__(self, name):
        self.__delitem__(name)

    @classmethod
    def pack(cls, name='args', target=0, unpack_kwargs=False, store_kwargs=True, ignore_first=True, ignore=[]):
        '''
        Pack all function arguments (Ordered) and store them on self.[name] property

        Args:
            name: (str) property name
            target: (None or int or str) the target object the parameter pack will be attached to
                int -> position arg, where 0 commonly refers to `self` or `cls` (first positional arg) for class method
                str -> arg name
                None -> the parameter pack is attached on method
            unpack_kwargs: (bool) whether to unpack the variable-length keyword arguments
            store_kwargs: (bool) whether to store whole variable-length keyword arguments on self.[name].[kwargs]
            ignore_first: (bool) whether to ignore the first variable. This is usually used to avoid storing `self` or `cls`
            ignore: (a list of str) a list of variable names that should be ignored

        Returns:
            a wrapped function

        

        for example, we create a class as follows:
        
        >>> class MyClass():
        ...
        ...     @ParameterPack.pack(name='pack')   # name: property name on which the parameter pack is stored
        ...     def __init__(self, x, y, z, name=None, **kwargs):
        ...         pass

        then, we construct an instance by calling it:

        >>> my_class = MyClass(1, 2, 3, m=10, n=20)

        The ParameterPack.pack will pack all of the arguments listed in __init__(...) and store them on my_class.pack,
        which outputs the following contents if we print it out:

        >>> print(my_class.pack)
        ParameterPack([('x', 1), ('y', 2), ('z', 3), ('name', None), ('kwargs', {'m':10, 'n':20})])

        Notice that if we set `unpack_kwargs` to True, then the kwargs as well as ('m', 10), ('n': 20) will all be stored 
        in the ParameterPack. If we set `store_kwargs` to False, then the kwargs will not be stored. Set `ignore_first`
        to True, the first argument (which, in this case, is `self`) will be ignored.

        We can unpack them in the same order as defined in the function signature:

        >>> x, y, z, name, kwargs = my_class.pack
        >>> print('x={}/y={}/z={}/name={}/kwargs={}'.format(x, y, z, name, kwargs))
        x=1/y=2/z=3/name=None/kwargs={'m':10, 'n':20}



        example usage:

        This function is very useful when your function/class accepts too many variables and you are lazy to assign them one by
        one to your function/class. The following example shows a class funciton with a bunch of arguments that you must assign
        them to `self` one by one without using this function:

        >>> class MyClass():
        ...     def __init__(self, a, b, c, d, e, f, g, h, i, j, k, l, m, n, o, p, q, r, s, t, u, v, w, x, y, z, **kwargs):
        ...         self.a = a
        ...         self.b = b
        ...         self.c = c
        ...         self.d = d
        ...         # ... 6 MONTHS LATER ...
        ...         self.z = z
        ...         self.kwargs = kwargs
        ...     def print_partial_args(self):
        ...         # redundent `self`
        ...         print(self.a, self.b, self.c, self.d, self.e, self.f, self.g)

        With `ParameterPack.pack`, things will get easier:

        >>> class MyClass():
        ...     @ParameterPack.pack(name='args')
        ...     def __init__(self, a, b, c, d, e, f, g, h, i, j, k, l, m, n, o, p, q, r, s, t, u, v, w, x, y, z, **kwargs):
        ...         pass
        ...     def print_partial_args(self):
        ...         a, b, c, d, e, f, g, *_ = self.args
        ...         print(a, b, c, d, e, f, g)

        
        '''



        def _wrapper(method):

            target_object = target
            
            sign = inspect.signature(method)
            kwpair_list = []
            kwargs_name = None
            need_unpack_kwargs = False
            unpack_kwargs_code = ''
            setattr_package_code = ''
            
            for idx, param in enumerate(sign.parameters.values()):
                

                # if target is int, get target name
                if isinstance(target_object, int) and idx == target:
                    target_object = param.name
                
                # ignore the first argument
                if idx == 0 and ignore_first:
                    continue

                # ignore arguments listed in the ignore list
                if param.name in ignore:
                    continue

                # handle **kwargs
                if param.kind == param.VAR_KEYWORD:

                    if store_kwargs:
                        kwpair_list.append("('{0}', {0})".format(param.name, param.name))
                    kwargs_name = param.name
                    need_unpack_kwargs = unpack_kwargs

                else:
                    kwpair_list.append("('{0}', {0})".format(param.name, param.name))


            if (not method.__name__[0].isalpha()) or method.__name__[0].isupper():
                func_name = '_ParameterPack{}'.format(method.__name__)
            else:
                func_name = '_ParameterPack_{}'.format(method.__name__)


            # if target is not None, the parameter pack will be attached in the forged wrapper_method
            # otherwise, the parameter pack is attached in _parameterpack__init__
            if target_object is not None:
                if (not isinstance(target_object, str)) or (target_object not in sign.parameters.keys()):
                    raise RuntimeError('Unknown target: {}'.format(target_object))

                # generate code for setattr
                setattr_package_code = cls._setattr_package_scode_template.format(target=target_object, property=name)


            # generate code for unpacking kwargs
            if need_unpack_kwargs:
                unpack_kwargs_code = cls._unpack_kwargs_scode_template.format(kwargs_name=kwargs_name)

            # === forging function ===
            source_vars = {
                'name': func_name,
                'signature': str(sign),
                'kwpair_list': ', '.join(kwpair_list),
                'unpack_kwargs_code': unpack_kwargs_code,
                'setattr_package_code': setattr_package_code,
            }

            namespace = {'cls': cls}

            wrapper_method = _forge_func(func_name, 
                                         cls._parameterpack_scode_template, 
                                         source_vars, 
                                         namespace)



            @functools.wraps(method)
            def _parameterpack__wrapped__(*args, **kwargs):
                package = wrapper_method(*args, **kwargs)

                # if target is None, attach to method
                if target is None:
                    setattr(method, name, package)

                return method(*args, **kwargs)

            # assign attributes
            # (! __wrapped__ will be eliminated)
            _parameterpack__wrapped__.__dict__ = method.__dict__


            return _parameterpack__wrapped__

        return _wrapper


'''
argshandler

Example

>>> class SubA(argshandler(sig='self, b, c')):
...    def __init__(self, _self, b, c, **kwargs):
...        super(SubA, self).__init__(_self, b, c)

>>> class A():
...    def __init__(self):
...        pass
...    @SubA.serve(args=['self', 'b', 'c'], callback=lambda *args, **kwargs: args[0])
...    def func(self, a, b, *args, c, d=None, **kwargs):
...        print(a, b, args, c, d, kwargs)
...    def create_subA(self, b, c):
...        return SubA(self, b, c)

>>> a = A()
>>> a.create_subA(b='b', c='c').func('a', 1, 2, 3, d='dd', foo='bar')

'''


class _all:
    def __str__(self):
        return 'all'

class _self:
    def __str__(self):
        return 'self'

def _argshandler__init__(self, *args, **kwargs):
    self._argshandler_bound_args = self._handler_sig.bind(*args, **kwargs)
    self._argshandler_bound_args.apply_defaults()

def _argshandler_serve(cls, args=_all, callback=_self):
    '''
    serve

    Args:
        cls: class object
        args: (list of str) argument name to serve
        callback: (Function) callback function
    '''
    if args is _all:
        args = list(cls._handler_sig.parameters.keys())
        #args = list(self._argshandler_bound_args.arguments.keys())

    def _generate_func(func, callback):
        '''
        Generate function
        Args:
            func: (Function) target function
            callback: (Function) callback function
        '''

        _argshandler_func_scode_template='''\
def _gened_func{signature}:

    default_params = _argshandler_self._argshandler_bound_args.arguments
    params = {dictionarize_code}
    default_params.update(params)
    
    boundargs = inspect.BoundArguments(func_sig, default_params)

    args = boundargs.args
    kwargs = boundargs.kwargs

    returns = _gened_func.func(*args, **kwargs)

    {callback_code}
'''
        func_sig = inspect.signature(func)
        target_args = [inspect.Parameter('_argshandler_self', inspect.Parameter.POSITIONAL_OR_KEYWORD)]

        # remove not served args
        for arg in func_sig.parameters.keys():
            if arg not in args:
                target_args.append(func_sig.parameters[arg])


        # create signature
        target_sig = func_sig.replace(parameters=target_args)
        target_sig_no_self = func_sig.replace(parameters=target_args[1:])

        # gen dictionarize
        param_list = []
        for idx, (name, param) in enumerate(target_sig_no_self.parameters.items()):
            
            param_list.append('({0!r}, {0})'.format(name))

        
        dictionarize_code = '_dict([' + ', '.join(param_list) + '])'


        # callback
        if callback is None:
            callback_code = 'return returns'
        elif callback is _self:
            callback_code = 'return _argshandler_self'
        else:
            callback_code = 'return callback(_argshandler_self, returns, *args, **kwargs)'


        kwargs_dict = {
            'signature': str(target_sig),
            'dictionarize_code': dictionarize_code,
            'callback_code': callback_code
        }

        namespace_dict = locals()
        namespace_dict['callback'] = callback
        namespace_dict['func_sig'] = func_sig
        namespace_dict['signature'] = target_sig
        namespace_dict['_dict'] = OrderedDict
        namespace_dict['inspect'] = inspect

        gened_func = _forge_func('_gened_func', 
                                 _argshandler_func_scode_template, 
                                 kwargs_dict, 
                                 namespace_dict)

        gened_func.signature = target_sig
        gened_func.func = func
        gened_func.func_sig = func_sig
        gened_func.callback = callback

        return gened_func

    def _update_func(gen_func, target_obj=None, ori_func=None):

        # update func info
        if ori_func is not None:
            if getattr(ori_func, '__name__', None):
                setattr(gen_func, '__name__', ori_func.__name__)

            if getattr(ori_func, '__doc__', None):
                setattr(gen_func, '__doc__', ori_func.__doc__)

        if target_obj is not None:
            setattr(gen_func, '__qualname__', '.'.join([target_obj.__qualname__, gen_func.__name__]))
            setattr(gen_func, '__module__', target_obj.__module__)


    def _attach_func(target_obj, gen_func, ismethod=True):

        #if ismethod:
        #    setattr(target_obj, gen_func.__name__, types.MethodType(gen_func, target_obj))
        #else:
        setattr(target_obj, gen_func.__name__, gen_func)

    def _wrapper(func):

        gened_func = _generate_func(func, callback)
        _update_func(gened_func, cls, func)
        _attach_func(cls, gened_func)

        return func

    return _wrapper



def argshandler(sig=None, baseclass=()):
    # create signature
    if isinstance(sig, str):
        lb = eval('lambda {sign}: None'.format(sign=sig))
        sig = inspect.signature(lb)

    if sig is None:
        sig = inspect.signature(lambda *args, **kwargs: None)

    assert isinstance(sig, inspect.Signature), 'sig must be an inspect.Signature'

    return type('ArgsHandler',
                baseclass,
                {'_handler_sig': sig,
                 '__init__': _argshandler__init__,
                 'serve': classmethod(_argshandler_serve)})

