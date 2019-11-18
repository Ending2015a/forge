from forge import dictionarize



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