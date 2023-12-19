moduledir = python_dir / 'hyperplane'

blueprints = custom_target('blueprints',
  input: files(
    'gtk/help-overlay.blp',
    'gtk/item.blp',
    'gtk/items-page.blp',
    'gtk/preferences.blp',
    'gtk/tag-row.blp',
    'gtk/window.blp',
  ),
  output: '.',
  command: [find_program('blueprint-compiler'), 'batch-compile', '@OUTPUT@', '@CURRENT_SOURCE_DIR@', '@INPUT@'],
)

gnome.compile_resources('hyperplane',
  configure_file(
    input: 'hyperplane.gresource.xml.in',
    output: 'hyperplane.gresource.xml',
    configuration: conf
  ),
  gresource_bundle: true,
  install: true,
  install_dir: pkgdatadir,
  dependencies: blueprints,
)

configure_file(
  input: 'hyperplane.in',
  output: 'hyperplane',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'r-xr--r--'
)

install_subdir('utils', install_dir: moduledir)
install_subdir('logging', install_dir: moduledir)

if profile == 'development'
  install_subdir('devel', install_dir: moduledir)
endif

hyperplane_sources = [
  '__init__.py',
  'file_properties.py',
  'item_filter.py',
  'item_sorter.py',
  'item.py',
  'items_page.py',
  'main.py',
  'navigation_bin.py',
  'postmaster_general.py',
  'preferences.py',
  'properties.py',
  'tag_row.py',
  'window.py',
  configure_file(
    input: 'shared.py.in',
    output: 'shared.py',
    configuration: conf
  )
]

install_data(hyperplane_sources, install_dir: moduledir)
