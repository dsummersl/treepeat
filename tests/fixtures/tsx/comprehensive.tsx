// This is a comment that should be removed
import React from 'react';
import { useState } from 'react';

/* Multi-line comment
   that should also be removed */

interface GreetingProps {
  name: string;
}

// Simple functional component with typed props
function Greeting({ name }: GreetingProps) {
  return <h1>Hello, {name}</h1>;
}

interface CounterProps {
  initialCount: number;
}

// Arrow function component with typed props
const Counter = ({ initialCount }: CounterProps) => {
  const [count, setCount] = useState<number>(initialCount);

  const increment = (): void => {
    setCount(count + 1);
  };

  return (
    <div className="counter">
      <p>Count: {count}</p>
      <button onClick={increment}>Increment</button>
    </div>
  );
};

interface Item {
  id: string;
  title: string;
  description: string;
}

interface ItemListProps {
  items: Item[];
  loading: boolean;
}

// Component with a list rendering pattern
const ItemList = ({ items, loading }: ItemListProps) => {
  return (
    <div class={loading ? 'opacity-75' : ''}>
      {items.map(item => (
        <div key={item.id} class="mb-4">
          <h3 class="font-semibold">{item.title}</h3>
          <p class="text-gray-600">{item.description}</p>
          <a href={`/items/${item.id}`} class="text-blue-500 hover:underline">
            View Details
          </a>
        </div>
      ))}
    </div>
  );
};

interface UserProfileProps {
  name: string;
  bio: string;
}

interface UserProfileState {
  expanded: boolean;
}

// Class component with types
class UserProfile extends React.Component<UserProfileProps, UserProfileState> {
  constructor(props: UserProfileProps) {
    super(props);
    this.state = { expanded: false };
  }

  toggle(): void {
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
