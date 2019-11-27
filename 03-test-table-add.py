from file import *
from file.table import TableFile
from file.paging import INVALID_OFF
from file.valuetype import Float32

types = [vt.SMALLINT, vt.TEXT, vt.FLOAT, vt.TINYINT]

#Tag ID     Name     Weight(kg)    Age (years)
data = ((933,   b'Rover',   Float32(20.6), 4),
        (8326,  b'Spot',    Float32(10.8), 7),
        (8326,  b'Spot',    Float32(10.8), 7),
        (8326,  b'Spot',    Float32(10.8), 7),
        (8326,  b'Spot',    Float32(10.8), 7),
        (8326,  b'Spot',    Float32(10.8), 7),
        (8326,  b'Spot',    Float32(10.8), 7),
        (8326,  b'Spot',    Float32(10.8), 7),
        (8326,  b'Spot',    Float32(10.8), 7),
        (8326,  b'Spot',    Float32(10.8), 7),
        (8326,  b'Spot',    Float32(10.8), 7),
        (8326,  b'Spot',    Float32(10.8), 7),
        (8326,  b'Spot',    Float32(10.8), 7),
        (8326,  b'Spot',    Float32(10.8), 7),
        (8326,  b'Spot',    Float32(10.8), 7),
        (5359,  b'Lucky',   Float32(31.2), 5),
        (10355, b'Dinky',   Float32(4.8),  11),
        (7757,  b'Bruiser', Float32(42.0), 6), 
        (3597,  b'Patch',   Float32(29.6), 9), 
        (202,   b'Prince',  Float32(16.6), 7), 
        (1630,  b'Bubbles', Float32(7.1),  11),
        (1223,  b'Peanut',  Float32(14.3), 2))

dbfile = TableFile(open('dogs.tbl', 'w+b'), types, 128, last_rowid = 0, 
        root_page = INVALID_OFF)
for i in range(len(data)):
    dbfile.add(data[i])
    for j in range(dbfile.next_page()):
        print(repr(dbfile.read_page(j)))
    input('************* Next... *****************')


