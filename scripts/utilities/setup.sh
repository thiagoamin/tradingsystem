#!/bin/bash

# Install clang-format
if [[ "$OSTYPE" == "darwin"* ]]; then
    brew install clang-format@17
elif [[ "$OSTYPE" == "linux"* ]]; then
    sudo apt-get install -y clang-format-17
fi

# Add other dependencies