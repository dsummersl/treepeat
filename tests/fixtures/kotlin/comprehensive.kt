package com.example

import java.util.*

/**
 * A comprehensive Kotlin sample for testing similarity detection.
 */
class Comprehensive(val name: String) {

    // A method that will have a duplicate
    fun calculateSum(a: Int, b: Int): Int {
        val result = a + b
        println("Calculating sum: $result")
        return result
    }

    fun greet() {
        val flag = true
        println("Hello, $name")
    }
}

class AnotherClass {
    // Duplicate of calculateSum in Comprehensive
    fun mySum(x: Int, y: Int): Int {
        val z = x + y
        println("Calculating sum: $z")
        return z
    }
}
