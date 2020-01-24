from forge import dictionarize
from forge import argshandler


# a, b, c: positional_or_keyword without default value
# *args: var_positional
# d: keyword_only
# e: keyword_only with default value
# **kwargs: var_keyword
def test(a, b, c, *args, d, e=10, **kwargs):
    print('a={}, b={}, c={}, d={}, e={}'.format(a, b, c, d, e))
    print('args: {}'.format(args))
    print('kwargs: {}'.format(kwargs))


print(' === test positional_or_keyword "a", "b" === ')
C = dictionarize(test, inputs=['a', 'b'])

print(' ::: source code:')
print(C._forge_source)

print(' ::: create Test(3, 4, 5, d=6, hello=\'CCCC\'): ')
c = C(3, 4, 5, d=6, hello='CCCC')

print(' ::: content:')
print(c)

print(' ::: call function: c(1, 2)')
c(1, 2)




print('\n\n === test var positional "a", "*args" ===')
C = dictionarize(test, inputs=['a', 'args'])

print(' ::: source code:')
print(C._forge_source)

print(' ::: create Test(3, 4, d=5, e=6, hello=\'CCCC\'): ')
c = C(3, 4, d=5, e=6, hello='CCCC')

print(' ::: content:')
print(c)

print(' ::: call function: c(1, 2, 3)')
c(1, 2, 3)




print('\n\n === test keyword only "a", "e" ===')
C = dictionarize(test, inputs=['a', 'e'])

print(' ::: source code:')
print(C._forge_source)

print(' ::: create Test(3, 4, 5, d=6, hello=\'CCCC\'): ')
c = C(3, 4, 5, d=6, hello='CCCC')

print(' ::: content:')
print(c)

print(' ::: call function: c(1, e=2)')
c(1, e=2)


from forge import ParameterPack

class A():
    @ParameterPack.pack(name='args')
    def __init__(self, a, b, *args, d, e=20, f=30, **kwargs):

        pass

    def print_args(self):
        print(self.args)

    def print_kwargs(self):
        a, b, args, d, e, *_ = self.args

        print('{}/{}/{}/{}/{}'.format(a, b, d, e, args))


a = A(1, 2, 3, 4, 5, 6, d=7, hello='hhh')

a.print_args()
a.print_kwargs()

@ParameterPack.pack(name='args', target=None)
def method2(a, b, *args, d, e=20, f=30, **kwargs):
    print('in method2: ', method2.args)


@ParameterPack.pack(name='args', target=None)
def method1(a, b, *args, d, e=20, f=30, **kwargs):
    print('begin method1: ', method1.args)
    method2(a, b, *args, d=d, e=e, f=f, hello='method2')

    print('method1.args is method2.args: {}'.format(method1.args is method2.args))
    print('end method1: ', method1.args)


method1(1, 2, 3, 4, 5, 6, d=7, e=100, f=200, hello='method1')


print('\n ------ argshandler ------ \n')

class SubA(argshandler(sig='self, b, c')):
    def __init__(self, _self, b, c, **kwargs):
        super(SubA, self).__init__(_self, b, c)

class A():
    @SubA.serve()
    def func(self, a, b, *args, c, d=None, **kwargs):
        print('a=', a)
        print('b=', b)
        print('args=', args)
        print('c=', c)
        print('d=', d)
        print('kwargs=', kwargs)

    def sub(self, b, c):
        return SubA(self, b, c)


sub = A().sub(b='bb', c='cc')

for k in dir(SubA.func):
    print('{}: {}'.format(k, getattr(SubA.func, k, None)))

print('\n --- \n')
for k in dir(sub.func):
    print('{}: {}'.format(k, getattr(sub.func, k, None)))

sub.func('aa', 1, 2, 3, d='dd', foo='bar', hello='world')
