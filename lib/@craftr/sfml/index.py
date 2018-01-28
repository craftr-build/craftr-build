
import craftr, {path} from 'craftr'
import cxx from '@craftr/cxx'
import {pkg_config} from '@craftr/pkg-config'

version = craftr.options.get('sfml.version', '2.4.2')
binary_dir = craftr.options.get('sfml.binary_dir', None)
static = craftr.options.get('sfml.static', True)
debug = craftr.options.get('sfml.debug', not craftr.is_release)

if cxx.compiler.id in ('msvc', 'mingw'):

  craftr.options.setdefault('cxx.static_runtime', False)

  if not binary_dir:
    # Find the appropriate download URL.
    bit = 32 if cxx.compiler.is32bit else 64
    if cxx.compiler.id == 'msvc':
      if cxx.compiler.toolkit.version <= 110:
        vcv = 'vc11'
      elif cxx.compiler.toolkit.version <= 120:
        vcv = 'vc12'
      else:
        vcv = 'vc14'
      url = 'https://www.sfml-dev.org/files/SFML-{version}-windows-{vcv}-{bit}-bit.zip'
    else:
      url = 'https://www.sfml-dev.org/files/SFML-{version}-windows-gcc-6.1.0-mingw-{bit}-bit.zip'
    url = url.format(**globals())

    # Download and unpack the archive.
    binary_dir = path.abs(path.join(craftr.get_source_archive(url), 'SFML-' + version))

  ssfx = '-s' if static else ''
  dsfx = '-d' if debug else ''

  sfml = cxx.prebuilt(
    name = 'sfml',
    includes = [craftr.path.join(binary_dir, 'include')],
    defines = ['SFML_STATIC'] if static else [],
    libpath = [craftr.path.join(binary_dir, 'lib')],
    syslibs = [x.format(**globals()) for x in [
      'sfml-main{dsfx}',
      'sfml-audio{ssfx}{dsfx}',
      'sfml-graphics{ssfx}{dsfx}',
      'sfml-network{ssfx}{dsfx}',
      'sfml-window{ssfx}{dsfx}',
      'sfml-system{ssfx}{dsfx}',
      'opengl32',
      'openal32',
      'freetype',
      'jpeg',
      'flac',
      'vorbisenc',
      'vorbisfile',
      'vorbis',
      'ogg',
      # Windows specific
      'ws2_32',
      'winmm',
      'gdi32',
      'user32',
      'advapi32'
    ]]
  )

else:
  pkg_config('SFML-all', 'sfml', static=static)