use std::collections::HashMap;

extern crate serde;

// Shape types for area/perimeter calculation
/// A circle defined by its radius.
#[derive(Debug, Clone)]
pub struct Circle {
    pub radius: f64,
    pub color: String,
}

/// A rectangle defined by its dimensions.
#[derive(Debug, Clone)]
pub struct Rectangle {
    pub width: f64,
    pub height: f64,
    pub color: String,
}

pub trait Shape {
    fn area(&self) -> f64;
    fn perimeter(&self) -> f64;
}

impl Shape for Circle {
    /* Compute circle area */
    fn area(&self) -> f64 {
        std::f64::consts::PI * self.radius * self.radius
    }

    fn perimeter(&self) -> f64 {
        2.0 * std::f64::consts::PI * self.radius
    }
}

impl Shape for Rectangle {
    // Structurally similar to Circle::area but different formula
    fn area(&self) -> f64 {
        self.width * self.height
    }

    fn perimeter(&self) -> f64 {
        2.0 * (self.width + self.height)
    }
}

/// Sums all elements of a slice of integers.
pub fn calculate_sum(numbers: &[i32]) -> i32 {
    let mut total = 0;
    for num in numbers {
        total += num;
    }
    total
}

/// Multiplies all elements of a slice of integers.
pub fn calculate_product(numbers: &[i32]) -> i32 {
    let mut product = 1;
    for num in numbers {
        product *= num;
    }
    product
}

pub enum Color {
    Red,
    Green,
    Blue,
}

/// Returns the Fibonacci number at position n (recursive).
pub fn fibonacci(n: u32) -> u64 {
    if n <= 1 {
        return n as u64;
    }
    fibonacci(n - 1) + fibonacci(n - 2)
}

/// Returns the Fibonacci number at position n (iterative).
pub fn fibonacci_iterative(n: u32) -> u64 {
    if n <= 1 {
        return n as u64;
    }
    let mut a: u64 = 0;
    let mut b: u64 = 1;
    for _ in 2..=n {
        let tmp = a + b;
        a = b;
        b = tmp;
    }
    b
}

/// Searches a slice linearly for a target value, returning its index.
pub fn search_linear(arr: &[i32], target: i32) -> Option<usize> {
    for (i, &val) in arr.iter().enumerate() {
        if val == target {
            return Some(i);
        }
    }
    None
}

/// A unique function with no structural counterpart.
pub fn build_index(items: &[String]) -> HashMap<String, usize> {
    let mut index = HashMap::new();
    for (i, item) in items.iter().enumerate() {
        index.insert(item.clone(), i);
    }
    index
}

/// Exercises match expressions and enum variants.
pub fn color_to_hex(color: Color) -> &'static str {
    match color {
        Color::Red => "#FF0000",
        Color::Green => "#00FF00",
        Color::Blue => "#0000FF",
    }
}

/// Generic function — exercises type parameter syntax.
pub fn find_max<T: PartialOrd>(items: &[T]) -> Option<&T> {
    let mut max = items.first()?;
    for item in items.iter() {
        if item > max {
            max = item;
        }
    }
    Some(max)
}

/// Exercises explicit non-static lifetime annotation.
pub fn first_word<'a>(s: &'a str) -> &'a str {
    match s.find(' ') {
        Some(i) => &s[..i],
        None => s,
    }
}

/// Async function — exercises the async fn syntax.
pub async fn fetch_value(key: &str) -> Option<String> {
    if key.is_empty() {
        return None;
    }
    Some(key.to_uppercase())
}

/// Exercises macro_rules! definitions as an extraction target.
macro_rules! assert_some {
    ($expr:expr) => {
        assert!($expr.is_some(), "expected Some, got None");
    };
}
