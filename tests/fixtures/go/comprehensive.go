package main

import (
	"fmt"
	"math"
	"strings"
)

// Circle represents a circle shape with a radius.
type Circle struct {
	Radius float64
	Color  string
}

// Area calculates the area of a circle.
func (c Circle) Area() float64 {
	return math.Pi * c.Radius * c.Radius
}

// Perimeter calculates the perimeter of a circle.
func (c Circle) Perimeter() float64 {
	return 2 * math.Pi * c.Radius
}

// Rectangle represents a rectangular shape.
type Rectangle struct {
	Width  float64
	Height float64
	Color  string
}

// Area calculates the area of a rectangle.
func (r Rectangle) Area() float64 {
	return r.Width * r.Height
}

// Perimeter calculates the perimeter of a rectangle.
func (r Rectangle) Perimeter() float64 {
	return 2 * (r.Width + r.Height)
}

// CalculateSum adds all elements in a slice of integers.
func CalculateSum(numbers []int) int {
	total := 0
	for _, num := range numbers {
		total += num
	}
	return total
}

// CalculateProduct multiplies all elements in a slice of integers.
func CalculateProduct(numbers []int) int {
	product := 1
	for _, num := range numbers {
		product *= num
	}
	return product
}

// FilterEvenNumbers returns only even numbers from a slice.
func FilterEvenNumbers(numbers []int) []int {
	result := []int{}
	for _, num := range numbers {
		if num%2 == 0 {
			result = append(result, num)
		}
	}
	return result
}

// FilterOddNumbers returns only odd numbers from a slice.
func FilterOddNumbers(numbers []int) []int {
	result := []int{}
	for _, num := range numbers {
		if num%2 != 0 {
			result = append(result, num)
		}
	}
	return result
}

// ProcessString converts a string to uppercase and trims whitespace.
func ProcessString(input string) string {
	trimmed := strings.TrimSpace(input)
	upper := strings.ToUpper(trimmed)
	return upper
}

// ProcessStringLower converts a string to lowercase and trims whitespace.
func ProcessStringLower(input string) string {
	trimmed := strings.TrimSpace(input)
	lower := strings.ToLower(trimmed)
	return lower
}

// User represents a user in the system.
type User struct {
	ID       int
	Username string
	Email    string
	Active   bool
}

// NewUser creates a new user with the given details.
func NewUser(id int, username, email string) *User {
	return &User{
		ID:       id,
		Username: username,
		Email:    email,
		Active:   true,
	}
}

// Validate checks if the user has valid data.
func (u *User) Validate() bool {
	if u.Username == "" {
		return false
	}
	if u.Email == "" {
		return false
	}
	if u.ID <= 0 {
		return false
	}
	return true
}

// Deactivate marks the user as inactive.
func (u *User) Deactivate() {
	u.Active = false
}

// Activate marks the user as active.
func (u *User) Activate() {
	u.Active = true
}

// Fibonacci generates the nth Fibonacci number recursively.
func Fibonacci(n int) int {
	if n <= 1 {
		return n
	}
	return Fibonacci(n-1) + Fibonacci(n-2)
}

// FibonacciIterative generates the nth Fibonacci number iteratively.
func FibonacciIterative(n int) int {
	if n <= 1 {
		return n
	}
	a, b := 0, 1
	for i := 2; i <= n; i++ {
		a, b = b, a+b
	}
	return b
}

// SearchLinear performs a linear search on a slice.
func SearchLinear(arr []int, target int) int {
	for i, val := range arr {
		if val == target {
			return i
		}
	}
	return -1
}

// SearchBinary performs a binary search on a sorted slice.
func SearchBinary(arr []int, target int) int {
	left, right := 0, len(arr)-1
	for left <= right {
		mid := (left + right) / 2
		if arr[mid] == target {
			return mid
		} else if arr[mid] < target {
			left = mid + 1
		} else {
			right = mid - 1
		}
	}
	return -1
}

// Constants for configuration.
const (
	MaxRetries     = 3
	TimeoutSeconds = 30
	DefaultPort    = 8080
)

// Variables for global state.
var (
	serverRunning bool
	connectionCount int
)

// main demonstrates usage of the functions above.
func main() {
	circle := Circle{Radius: 5.0, Color: "red"}
	fmt.Printf("Circle area: %.2f\n", circle.Area())

	rect := Rectangle{Width: 10.0, Height: 5.0, Color: "blue"}
	fmt.Printf("Rectangle area: %.2f\n", rect.Area())

	numbers := []int{1, 2, 3, 4, 5}
	sum := CalculateSum(numbers)
	fmt.Printf("Sum: %d\n", sum)

	evens := FilterEvenNumbers(numbers)
	fmt.Printf("Even numbers: %v\n", evens)

	user := NewUser(1, "john_doe", "john@example.com")
	if user.Validate() {
		fmt.Println("User is valid")
	}

	fib := Fibonacci(10)
	fmt.Printf("Fibonacci(10): %d\n", fib)

	index := SearchLinear(numbers, 3)
	fmt.Printf("Found at index: %d\n", index)
}
