#!/usr/bin/env python3
"""Compile gettext catalogs like ``pybabel compile``, honoring no-python-format.

Babel force-adds the ``python-format`` flag to any msgid that merely looks like
a printf format string (e.g. "50% for percentage" -> false placeholder "% f")
and ignores the standard GNU gettext ``no-python-format`` flag, so its
placeholder check cannot be suppressed the standard way and fails the build on
false positives.  This wrapper restores the GNU semantics: messages explicitly
flagged ``no-python-format`` in the .po file are exempted from the placeholder
check.  Every other catalog check still runs and still fails the build.

Usage (drop-in for the previous pybabel invocations):
    python3 scripts/translations/compile_catalogs.py -d ./website/translations
    python3 scripts/translations/compile_catalogs.py -D django -d ./admin/translations
"""
import argparse
import os
import sys

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po


def compile_directory(directory, domain):
    n_errors = 0
    n_catalogs = 0
    for locale in sorted(os.listdir(directory)):
        po_path = os.path.join(directory, locale, 'LC_MESSAGES', domain + '.po')
        if not os.path.isfile(po_path):
            continue
        n_catalogs += 1
        with open(po_path, 'rb') as f:
            catalog = read_po(f, locale=locale, domain=domain)

        # Restore GNU gettext semantics: no-python-format wins over Babel's
        # regex-based auto-detection of the python-format flag.
        for message in catalog:
            if 'no-python-format' in message.flags:
                message.flags.discard('python-format')

        for message, errors in catalog.check():
            for error in errors:
                sys.stderr.write('error: %s:%s: %s\n' % (po_path, message.lineno, error))
                n_errors += 1

        if catalog.fuzzy:
            print('catalog %s is marked as fuzzy, skipping' % po_path)
            continue

        mo_path = po_path[:-3] + '.mo'
        print('compiling catalog %s to %s' % (po_path, mo_path))
        with open(mo_path, 'wb') as f:
            write_mo(f, catalog, use_fuzzy=False)
    return n_errors, n_catalogs


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('-d', '--directory', required=True,
                        help='base directory containing <locale>/LC_MESSAGES/<domain>.po')
    parser.add_argument('-D', '--domain', default='messages',
                        help='message domain (default: messages)')
    args = parser.parse_args()

    n_errors, n_catalogs = compile_directory(args.directory, args.domain)
    if n_catalogs == 0:
        sys.stderr.write('warning: no %s.po catalogs found under %s\n'
                         % (args.domain, args.directory))
    if n_errors:
        sys.stderr.write('%d errors encountered.\n' % n_errors)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
