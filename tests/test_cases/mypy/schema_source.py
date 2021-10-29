#!/usr/bin/env python

def main() -> None:
    import io
    from pathlib import Path
    from typing import cast, IO
    from xml.etree import ElementTree

    import xmlschema

    case_dir = Path(__file__).parent.parent
    col_xsd = case_dir.joinpath('examples/collection/collection.xsd')

    schema = xmlschema.XMLSchema10(str(col_xsd))
    print(f"{schema} from filepath")

    with open(str(col_xsd)) as fp:
        schema = xmlschema.XMLSchema10(fp)
    print(f"{schema} from open(filepath)")

    with open(str(col_xsd), mode='rb') as bfp:
        schema = xmlschema.XMLSchema10(bfp)
    print(f"{schema} from open(filepath, mode='rb'), mode binary")

    with col_xsd.open() as fp:
        schema = xmlschema.XMLSchema10(cast(IO[str], fp))
    print(f"{schema} from IO[str]")

    with col_xsd.open(mode='rb') as bfp:
        schema = xmlschema.XMLSchema10(cast(IO[str], bfp))
    print(f"{schema} from IO[bytes]")

    with col_xsd.open() as fp:
        schema = xmlschema.XMLSchema10(io.StringIO(fp.read()))
    print(f"{schema} from io.StringIO()")

    with col_xsd.open(mode='rb') as bfp:
        schema = xmlschema.XMLSchema10(io.BytesIO(bfp.read()))
    print(f"{schema} from io.BytesIO()")

    xt = ElementTree.parse(col_xsd)
    namespaces = {
        'xs': "http://www.w3.org/2001/XMLSchema",
        '': "http://example.com/ns/collection",
    }
    schema = xmlschema.XMLSchema10(xt, build=False)
    schema.namespaces.update(namespaces)  # FIXME? Provide an init argument?
    schema.build()
    print(f"{schema} from ElementTree.ElementTree")

    schema = xmlschema.XMLSchema10(xt.getroot(), build=False)
    schema.namespaces.update(namespaces)
    schema.build()
    print(f"{schema} from ElementTree.Element")

    schema = xmlschema.XMLSchema10(xmlschema.XMLResource(str(col_xsd)))
    print(f"{schema} from xmlschema.XMLResource()")


if __name__ == '__main__':
    main()
