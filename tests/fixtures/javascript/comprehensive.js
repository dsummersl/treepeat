// This is a comment that should be removed
import { SomeModule } from './module.js';
export { AnotherModule } from './another.js';

/* Multi-line comment
   that should also be removed */

// Test function declaration
function regularFunction(param1, param2) {
  // Comments inside functions
  const result = param1 + param2;
  const message = "This is a string literal";
  const number = 42;
  const templateStr = `Value is ${result}`;

  // Test collections
  const arr = [1, 2, 3];
  const obj = { key: "value", count: 10 };

  // Test expressions
  const binary = 5 + 3;
  const unary = !true;
  let counter = 0;
  counter++;
  const assignment = counter = 5;
  const ternary = counter > 0 ? "positive" : "negative";

  return result;
}

// Test function expression
const functionExpression = function(x) {
  return x * 2;
};

// Test arrow function
const arrowFunction = (a, b) => {
  return a - b;
};

// Test class with methods
class Calculator {
  constructor(initialValue) {
    this.value = initialValue;
  }

  // Test method definition
  add(amount) {
    this.value += amount;
    return this.value;
  }

  subtract(amount) {
    this.value -= amount;
    return this.value;
  }

  reset() {
    this.value = 0;
  }
}

export default Calculator;
