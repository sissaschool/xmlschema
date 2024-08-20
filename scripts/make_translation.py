#
# Copyright (c), 2016-2022, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
# type: ignore
#
"""Translation files generator utility."""

if __name__ == '__main__':
    import argparse
    import os
    import sys
    import subprocess
    from pathlib import Path

    COPYRIGHT_HOLDER = r", 2016, SISSA (International School for Advanced Studies)."

    parser = argparse.ArgumentParser(
        description="Translation files generator utility for xmlschema"
    )
    parser.add_argument(
        '-L', '--directory', metavar='LOCALE-DIR', type=str, default=None,
        help="use a custom locale directory (for extra local translations)"
    )
    parser.add_argument(
        '-t', '--template', action='store_true', default=False,
        help="generate xmlschema.pot template file"
    )
    parser.add_argument(
        '-u', '--update', action='store_true', default=False,
        help="update locale xmlschema.po file from xmlschema.pot template"
    )
    parser.add_argument(
        '-c', '--compile', action='store_true', default=False,
        help="generate xmlschema.mo file from locale xmlschema.po"
    )
    parser.add_argument('languages', type=str, nargs='*',
                        help="process locale files for languages")
    args = parser.parse_args()

    if args.directory is not None:
        locale_dir = Path(args.directory).resolve()
        os.chdir(Path(__file__).parent.parent)
        try:
            locale_dir = locale_dir.relative_to(os.getcwd())
        except ValueError:
            pass  # Not a subdir, use the absolute path.
    else:
        os.chdir(Path(__file__).parent.parent)
        locale_dir = Path('xmlschema/locale')
    assert locale_dir.is_dir(), 'locale directory not found!'

    package_dir = Path('xmlschema')
    assert package_dir.is_dir(), 'xmlschema/ package directory not found!'

    template_file = locale_dir.joinpath('xmlschema.pot')
    if args.template:
        print("+++ Generate the template file ...")

        status, xgettext_cmd = subprocess.getstatusoutput('which xgettext')
        assert status == 0, "xgettext command is not available!"

        cmd = [xgettext_cmd,
               f'--copyright-holder={COPYRIGHT_HOLDER}',
               '--package-name=xmlschema',
               '--from-code=UTF-8',
               '-o', str(template_file)]
        cmd.extend(str(path) for path in package_dir.glob('**/*.py'))
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        stderr = process.stderr.decode('utf-8').strip()
        if stderr:
            print(stderr)
            sys.exit(1)

        # .POT template file fixes
        with template_file.open() as fp:
            text = fp.read().replace('charset=CHARSET', 'charset=UTF-8', 1)
        with template_file.open(mode='w') as fp:
            fp.write(text)

        print(f'  ... file {str(template_file)} written\n')

    if not args.languages:
        print("No language code provided, exit ...")
        sys.exit()

    if args.update:
        status, msgmerge_cmd = subprocess.getstatusoutput('which msgmerge')
        assert status == 0, "msgmerge command is not available!"

        for lang in args.languages:
            print(f"+++ Update the .po file for language {lang!r}")

            po_file = locale_dir.joinpath(f'{lang}/LC_MESSAGES/xmlschema.po')
            if not po_file.exists():
                po_file.parent.mkdir(parents=True, exist_ok=True)

                status, msginit_cmd = subprocess.getstatusoutput('which msginit')
                assert status == 0, "msginit command is not available!"

                cmd = [msginit_cmd,
                       '-l', f'{lang}',
                       '-o', str(po_file),
                       '-i', str(template_file)]
                process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                stderr = process.stderr.decode('utf-8').strip()
                if stderr:
                    print(stderr)

                print(f'  ... file {str(po_file)} initialized\n')

            cmd = [msgmerge_cmd, '-o', str(po_file), str(po_file), str(template_file)]
            process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            stderr = process.stderr.decode('utf-8').strip()
            if 'done' not in stderr:
                print(stderr)
                sys.exit(1)

            print(f'  ... file {str(po_file)} updated\n')

    if args.compile:
        status, msgfmt_cmd = subprocess.getstatusoutput('which msgfmt')
        assert status == 0, "msgfmt command is not available!"

        for lang in args.languages:
            print(f"+++ Generate the .mo file for language {lang!r}")

            po_file = locale_dir.joinpath(f'{lang}/LC_MESSAGES/xmlschema.po')
            mo_file = locale_dir.joinpath(f'{lang}/LC_MESSAGES/xmlschema.mo')
            if not po_file.exists():
                print(f"  ... file {str(po_file)} doesn't exist!")
                sys.exit(1)

            cmd = [msgfmt_cmd, '-o', str(mo_file), str(po_file)]
            process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            stderr = process.stderr.decode('utf-8').strip()
            if stderr:
                print(stderr)
                sys.exit(1)

            print(f'  ... file {str(mo_file)} written\n')
