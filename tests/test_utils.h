#pragma once

#include <cstdlib>
#include <iostream>

#define REQUIRE(condition)                                      \
    do                                                          \
    {                                                           \
        if (!(condition))                                       \
        {                                                       \
            std::cerr                                           \
                << "Test failed: " << #condition << '\n'        \
                << "File: " << __FILE__ << '\n'                 \
                << "Line: " << __LINE__ << '\n';                \
                                                                \
            std::exit(EXIT_FAILURE);                            \
        }                                                       \
    } while (false)