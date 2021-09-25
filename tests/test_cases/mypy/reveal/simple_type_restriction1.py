#!/usr/bin/env python
from typing import TYPE_CHECKING


def main() -> None:
    from pathlib import Path
    import xmlschema
    from xmlschema.validators import XsdAtomicRestriction

    case_dir = Path(__file__).parent.parent.parent

    st_xsd = case_dir.joinpath('features/decoder/simple-types.xsd')
    schema = xmlschema.XMLSchema10(str(st_xsd))

    xsd_type: XsdAtomicRestriction = schema.types['typeB']
    if not TYPE_CHECKING:
        return

    reveal_type(schema.types['typeB'])
    reveal_type(xsd_type)
    reveal_type(xsd_type.validators)
    reveal_type(xsd_type.min_length)
    reveal_type(xsd_type.max_length)

    reveal_type(schema)
    reveal_type(xmlschema.XMLSchema10)


if __name__ == '__main__':
    main()
