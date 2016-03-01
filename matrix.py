#!/usr/bin/python

# Why don't we just use numpy?  Well, it's an extra dependency, and we don't
# need very much or very fast linear algebra.  So we'll roll our own...

import math

class Vector3(object):
    def __init__(self, (x, y, z)):
        self.data = tuple(float(r) for r in (x, y, z))

class Matrix3(object):
    def __init__(self, by_row):
        self.by_row = tuple(tuple(map(float, r)) for r in by_row)
    def __mul__(self, other):
        if isinstance(other, Vector3):
            return Vector3((sum(self.by_row[i][j] * other.data[j] for j in xrange(3)) for i in xrange(3)))
        if isinstance(other, Matrix3):
            return Matrix3(((sum(self.by_row[i][j] * other.by_row[j][k] for j in xrange(3)) for k in xrange(3)) for i in xrange(3)))
        return NotImplemented

def RotationMatrix(axis, angle):
    c = math.cos(angle)
    s = math.sin(angle)
    if axis == 0:
        return Matrix3(((1, 0, 0), (0, c, -s), (0, s, c)))
    if axis == 1:
        return Matrix3(((c, 0, s), (0, 1, 0), (-s, 0, c)))
    if axis == 2:
        return Matrix3(((c, -s, 0), (s, c, 0), (0, 0, 1)))
    raise ValueError(axis)
