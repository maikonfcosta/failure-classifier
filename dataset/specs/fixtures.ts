// Used only while building the dataset: the suite's own fixtures plus the network recorder.
import { test as base } from '../../fixtures';
import { withNetworkErrors } from './network-errors';

export const test = withNetworkErrors(base);
export { expect } from '@playwright/test';
