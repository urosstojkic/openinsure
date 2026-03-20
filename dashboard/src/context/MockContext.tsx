import { createContext, useContext, useState, type ReactNode } from 'react';

interface MockContextType {
  useMock: boolean;
  toggleMock: () => void;
}

const MockContext = createContext<MockContextType>({ useMock: false, toggleMock: () => {} });

export function MockProvider({ children }: { children: ReactNode }) {
  const [useMock, setUseMock] = useState(() => {
    return localStorage.getItem('openinsure_mock') === 'true';
  });

  const toggleMock = () => {
    const next = !useMock;
    setUseMock(next);
    localStorage.setItem('openinsure_mock', String(next));
    window.location.reload();
  };

  return <MockContext.Provider value={{ useMock, toggleMock }}>{children}</MockContext.Provider>;
}

export const useMockMode = () => useContext(MockContext);
