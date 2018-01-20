
namespace = 'cython'

import craftr from 'craftr'
import cython from '@craftr/cython'

cython.project(
  name = 'main',
  srcs = craftr.glob('*.pyx', excludes = ['Main.pyx']),
  main = 'Main.pyx',
  in_working_tree = False
)

cython.run(':main')
