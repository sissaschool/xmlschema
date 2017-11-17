From [issue #22](https://github.com/brunato/xmlschema/issues/22#issuecomment-345236067).

Core of the issue is described as follows:

> One thing I noticed is that the to_dict function is not consistent in how it
> creates values in the dictionary for sequences. The sequence can already be
> anticipated from the .xsd, so I would have expected those values to be within
> array structures no matter the number of sequence elements present in the
> parent xml element.

See xsd in `./xsd_string.xsd`.

See xml in `./xml_string_1.xml` and `./xml_string_2.xml`.

```` python
import xmlschema
xsd_schema = xmlschema.XMLSchema(xsd_string)
xml_data_1 = xsd_schema.to_dict(xml_string_1)
xml_data_2 = xsd_schema.to_dict(xml_string_2)
print(xml_data_1)

    {'bar':
      {'@name': 'bar_1', 'subject_name': 'Bar #1'}}
print(xml_data_2)

    {'bar':
      [{'@name': 'bar_1', 'subject_name': 'Bar #1'},
       {'@name': 'bar_2', 'subject_name': 'Bar #2'}]}
````

We would expect the output from each to contain a list; The first a list with one dictionary.
