import '@testing-library/jest-dom';
import React from 'react';
import { vi } from 'vitest';

vi.mock('react-chartjs-2', () => ({
  Line: (props: any) =>
    React.createElement('div', {
      'data-testid': 'mock-chart-line',
      'data-chart-data': JSON.stringify(props.data || {}),
    }, 'Mock Line Chart'),
  Bar: (props: any) =>
    React.createElement('div', {
      'data-testid': 'mock-chart-bar',
      'data-chart-data': JSON.stringify(props.data || {}),
    }, 'Mock Bar Chart'),
}));

