#!/usr/bin/env python

def main() -> None:
    from pathlib import Path
    import xmlschema
    from xmlschema.names import XSD_ENUMERATION
    from xmlschema.validators import XsdAtomicRestriction

    case_dir = Path(__file__).parent.parent

    st_xsd = case_dir.joinpath('features/decoder/simple-types.xsd')
    schema = xmlschema.XMLSchema10(str(st_xsd))

    xsd_type = schema.types['enum1']
    if isinstance(xsd_type, XsdAtomicRestriction):
        assert xsd_type.enumeration == ['one', 'two', 'three']

    facet = xsd_type.get_facet(XSD_ENUMERATION)
    print(facet)
    xsd_type.is_datetime()


if __name__ == '__main__':
    main()
