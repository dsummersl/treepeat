package com.example;

import java.util.List;
import java.util.ArrayList;

/**
 * A comprehensive Java sample for testing similarity detection.
 */
public class Comprehensive {
    private String name;

    public Comprehensive(String name) {
        this.name = name;
    }

    // A method that will have a duplicate
    public int calculateSum(int a, int b) {
        int result = a + b;
        System.out.println("Calculating sum: " + result);
        return result;
    }

    public void greet() {
        boolean flag = true;
        System.out.println("Hello, " + name);
    }
}

class AnotherClass {
    // Duplicate of calculateSum in Comprehensive
    public int mySum(int x, int y) {
        int z = x + y;
        System.out.println("Calculating sum: " + z);
        return z;
    }
}
