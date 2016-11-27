#!/usr/bin/python

# Why don't we just use numpy?  Well, it's an extra dependency, and we don't
# need very much or very fast linear algebra.  So we'll roll our own...

import math

class Vector3(object):
    def __init__(self, (x, y, z)):
        self.data = tuple(float(r) for r in (x, y, z))
    def __add__(self, other):
        return Vector3((a + b for a,b in zip(self.data, other.data)))
    def __sub__(self, other):
        return Vector3((a - b for a,b in zip(self.data, other.data)))
    def __rmul__(self, other):
        # scalar multiple
        return Vector3((a * other for a in self.data))
    def dot(self, other):
        # dot product
        return sum(a * b for a,b in zip(self.data, other.data))
    def cross(self, other):
        return Vector3((self.data[1] * other.data[2] - self.data[2] * other.data[1],
                        self.data[2] * other.data[0] - self.data[0] * other.data[2],
                        self.data[0] * other.data[1] - self.data[1] * other.data[0]))
    @property
    def x(self):
        return self.data[0]
    @property
    def y(self):
        return self.data[1]
    @property
    def z(self):
        return self.data[2]
    @classmethod
    def ex(cls):
        return cls((1, 0, 0))
    @classmethod
    def ey(cls):
        return cls((0, 1, 0))
    @classmethod
    def ez(cls):
        return cls((0, 0, 1))
    @property
    def mag(self):
        return math.sqrt(sum(a*a for a in self.data))
    @property
    def hat(self):
        return (1.0 / self.mag) * self
    def __str__(self):
        return '(%f, %f, %f)'%self.data

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
