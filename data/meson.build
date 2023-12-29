desktop_file = i18n.merge_file(
        input: configure_file(
          input: 'hu.kramo.Hyperplane.desktop.in',
          output: app_id + '.desktop.in',
          configuration: conf
        ),
       output: app_id + '.desktop',
         type: 'desktop',
       po_dir: '../po',
      install: true,
  install_dir: get_option('datadir') / 'applications'
)

desktop_utils = find_program('desktop-file-validate', required: false)
if desktop_utils.found()
  test('Validate desktop file', desktop_utils, args: [desktop_file])
endif

servicedir = get_option('prefix') / get_option('datadir') / 'dbus-1' / 'services'

service_conf = configuration_data()
service_conf.set('bindir', servicedir)

configure_file(
  input: 'org.freedesktop.FileManager1.service.in',
  output: 'org.freedesktop.FileManager1.service',
  configuration: service_conf,
  install_dir: servicedir
)


appstream_file = i18n.merge_file(
        input: configure_file(
          input: 'hu.kramo.Hyperplane.metainfo.xml.in',
          output: app_id + '.metainfo.xml.in',
          configuration: conf
        ),
       output: app_id + '.metainfo.xml',
       po_dir: '../po',
      install: true,
  install_dir: get_option('datadir') / 'metainfo'
)

appstreamcli = find_program('appstreamcli', required: false, disabler: true)
test('Validate appstream file', appstreamcli,
     args: ['validate', '--no-net', '--explain', appstream_file])

install_data(
  configure_file(
    input: 'hu.kramo.Hyperplane.gschema.xml.in',
    output: app_id + '.gschema.xml',
    configuration: conf
  ),
  install_dir: get_option('datadir') / 'glib-2.0' / 'schemas'
)

compile_schemas = find_program('glib-compile-schemas', required: false, disabler: true)
test('Validate schema file',
     compile_schemas,
     args: ['--strict', '--dry-run', meson.current_source_dir()])

subdir('icons')
