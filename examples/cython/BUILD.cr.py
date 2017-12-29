
import craftr from 'craftr'
import cython from 'craftr/lang/cython'

cython.project(
  name = 'main',
  srcs = craftr.glob('*.pyx', excludes = ['Main.pyx']),
  main = 'Main.pyx'
)

#cython.run(':main')