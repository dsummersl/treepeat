// This is a comment that should be removed
import React from 'react';
import { useState } from 'react';

/* Multi-line comment
   that should also be removed */

// Simple functional component
function Greeting(props) {
  return <h1>Hello, {props.name}</h1>;
}

// Arrow function component
const Counter = ({ initialCount }) => {
  const [count, setCount] = useState(initialCount);

  const increment = () => {
    setCount(count + 1);
  };

  return (
    <div className="counter">
      <p>Count: {count}</p>
      <button onClick={increment}>Increment</button>
    </div>
  );
};

// Class component
class UserProfile extends React.Component {
  constructor(props) {
    super(props);
    this.state = { expanded: false };
  }

  toggle() {
    this.setState({ expanded: !this.state.expanded });
  }

  render() {
    return (
      <div>
        <h2>{this.props.name}</h2>
        {this.state.expanded && <p>{this.props.bio}</p>}
        <button onClick={() => this.toggle()}>Toggle</button>
      </div>
    );
  }
}

export default UserProfile;
