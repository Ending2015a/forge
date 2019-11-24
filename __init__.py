# --- built in ---
import os
import sys
import time
import inspect
import logging
import functools

from collections import OrderedDict
# --- 3rd party ---


# --- my module ---


__all__ = [
    'dictionarize',
    'ParameterPack'
]


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
    

class ParameterPack(OrderedDict):
    '''
    ParameterPack

    It's a kind of named tuple, but implemented using OrderedDict.
    '''


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
        self.__dict__ = self

    def __iter__(self):
        yield from self.values()

    @classmethod
    def pack(cls, name='args', target=0, unpack_kwargs=False, store_kwargs=True, ignore_first=True, ignore=[]):
        '''
        Pack all function arguments (Ordered) and store them on self.[name] property

        Args:
            name: (str) property name
            target: (None or int or str) the target object the parameter pack will be attached to
                int -> position arg, where 0 commonly refers to 'self'/'cls' (first positional arg) for class method
                str -> arg name
                None -> the parameter pack will be attached on method
            unpack_kwargs: (bool) whether to unpack the variable-length keyword arguments
            store_kwargs: (bool) whether to store whole variable-length keyword arguments on self.[name].[kwargs]
            ignore_first: (bool) whether to ignore the first variable
            ignore: (a list of str) a list of variable names that should be ignored

        Returns:
            a wrapped function

        

        for example, we create a class as follows:
        
        >>> class MyClass():
        ...
        ...     @ParameterPack.pack(name='pack')   # name: property name in which the parameter pack will be stored
        ...     def __init__(self, x, y, z, name=None, **kwargs):
        ...         pass

        then, we construct an instance by calling it:

        >>> my_class = MyClass(1, 2, 3, m=10, n=20)

        The ParameterPack.pack will pack all of the arguments listed in __init__(...) and store them in my_class.pack,
        which will output the following contents if we print it out:

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

