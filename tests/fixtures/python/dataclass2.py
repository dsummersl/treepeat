# A file with two identical functions, but different names.
def one():
    """ A funtion that computes the sum of first ten natural numbers """
    total = 0
    for i in range(1, 11):
        total += i
    return total

def one_prime():
    """ A function that computes the sum of first ten natural numbers """
    sum = 0
    for value in range(1, 11):
        sum += value
    return sum
