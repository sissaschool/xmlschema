#!/bin/bash

echo "***************************************************************"
echo "xmlschema: run all tests with all available Python interpreters"
echo "***************************************************************"
echo

TESTS_DIR=$(dirname $0)
if [ -z $TESTS_DIR ]; then
    TESTS_DIR="."
fi

for PYTHON_CMD in python{2.7,3.3,3.4,3.5,3.6}; do
    if hash $PYTHON_CMD 2>/dev/null; then
        CMD="$PYTHON_CMD $TESTS_DIR/test_all.py"
        echo "# $CMD"
        $($CMD)
    	echo
    fi
done;

