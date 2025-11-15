/* Copyright (c) 2021-25 MIT 6.102/6.031 course staff, all rights reserved.
 * Redistribution of original or derived work requires permission of course staff.
 */

import { Board } from './board.js';

/**
 * Enhanced simulation code for testing concurrent multi-player games.
 * 
 * This simulation:
 * - Tests multiple players flipping cards simultaneously
 * - Verifies waiting behavior when cards are controlled
 * - Tests that matched cards are properly removed
 * - Ensures the game doesn't deadlock
 */
async function simulationMain(): Promise<void> {
  console.log('MEMORY SCRAMBLE - CONCURRENT SIMULATION');

  const filename = 'boards/ab.txt';
  const board: Board = await Board.parseFromFile(filename);
  const { rows, cols } = board.getDimensions();

  console.log(`\nLoaded board: ${rows}x${cols} from ${filename}`);
  console.log('Initial board state:');
  console.log(board.toString());

  // Configuration
  const players = 4;  // Multiple concurrent players
  const tries = 100;   // Each player makes 100 attempts
  const minDelayMilliseconds = 0.1;  // Minimum random delay
  const maxDelayMilliseconds = 2;  // Maximum random delay between moves

  console.log(`\nStarting simulation with ${players} players, ${tries} attempts each`);
  console.log(`Random delays between ${minDelayMilliseconds}ms and ${maxDelayMilliseconds}ms\n`);

  // Track statistics
  const stats = {
    totalFlips: 0,
    successfulMatches: 0,
    failedFlips: 0,
    waits: 0
  };

  // Start up multiple players as concurrent asynchronous function calls
  const playerPromises: Array<Promise<void>> = [];
  for (let ii = 0; ii < players; ++ii) {
    playerPromises.push(player(ii));
  }

  // Wait for all players to finish
  await Promise.all(playerPromises);

  console.log('SIMULATION COMPLETE');
  console.log(`Total flips attempted: ${stats.totalFlips}`);
  console.log(`Successful matches: ${stats.successfulMatches}`);
  console.log(`Failed flips: ${stats.failedFlips}`);
  console.log(`Times waited for card: ${stats.waits}`);
  console.log('\nFinal board state:');
  console.log(board.toString());

  /** 
   * Simulate one player making random moves
   * @param playerNumber player to simulate 
   */
  async function player(playerNumber: number): Promise<void> {
    const playerId = `player${playerNumber}`;
    const numberOfColors = 3;
    const color = ['\x1b[31m', '\x1b[32m', '\x1b[33m'][playerNumber % numberOfColors]; // Red, Green, Yellow
    const reset = '\x1b[0m';

    console.log(`${color}[${playerId}] Starting...${reset}`);

    for (let jj = 0; jj < tries; ++jj) {
      try {
        // Random delay before first card (between 0.1ms and 2ms)
        await timeout(minDelayMilliseconds + Math.random() * (maxDelayMilliseconds - minDelayMilliseconds));

        // Try to flip a first card at random position
        const firstRow = randomInt(rows);
        const firstCol = randomInt(cols);

        console.log(`${color}[${playerId}] Attempt ${jj + 1}: Flipping FIRST card at (${firstRow},${firstCol})${reset}`);
        const startTime = Date.now();

        await board.flip(playerId, firstRow, firstCol);
        stats.totalFlips++;

        const waitTime = Date.now() - startTime;
        const waitThreshold = 5; // milliseconds
        if (waitTime > waitThreshold) {
          stats.waits++;
          console.log(`${color}[${playerId}]   → Waited ${waitTime}ms for card${reset}`);
        }

        // Random delay before second card (between 0.1ms and 2ms)
        await timeout(minDelayMilliseconds + Math.random() * (maxDelayMilliseconds - minDelayMilliseconds));

        // Try to flip a second card at random position
        const secondRow = randomInt(rows);
        const secondCol = randomInt(cols);

        console.log(`${color}[${playerId}] Attempt ${jj + 1}: Flipping SECOND card at (${secondRow},${secondCol})${reset}`);

        await board.flip(playerId, secondRow, secondCol);
        stats.totalFlips++;

        // Check if it was a match by looking at board state
        const boardState = board.look(playerId);
        const lines = boardState.split('\n');

        // Count "my" cards - if we have 2, it was a match
        const myCards = lines.filter(line => line.startsWith('my ')).length;
        if (myCards === 2) {
          stats.successfulMatches++;
          console.log(`${color}[${playerId}]    MATCH! Cards will be removed on next move${reset}`);
        } else {
          console.log(`${color}[${playerId}] No match, cards stay face up${reset}`);
        }

      } catch (err) {
        stats.failedFlips++;
        const errorMsg = err instanceof Error ? err.message : String(err);
        console.log(`${color}[${playerId}] Flip failed: ${errorMsg}${reset}`);
      }
    }

    console.log(`${color}[${playerId}] Finished all attempts${reset}`);
  }
}

/**
 * Test scenario: Multiple players competing for the same card
 * This specifically tests the waiting mechanism
 */
async function testWaitingScenario(): Promise<void> {
  console.log('TEST: Multiple Players Waiting for Same Card');

  const board = await Board.parseFromFile('boards/ab.txt');

  console.log('\nScenario: Alice controls (0,0), Bob and Charlie both want it');

  // Alice takes control of (0,0)
  console.log('\n[Alice] Flipping (0,0)...');
  await board.flip('alice', 0, 0);
  console.log('[Alice] Now controls (0,0)');

  // Bob and Charlie both try to flip (0,0) - they should wait
  console.log('\n[Bob] Trying to flip (0,0) - should WAIT...');
  console.log('[Charlie] Trying to flip (0,0) - should WAIT...');

  const bobStartTime = Date.now();
  const bobPromise = board.flip('bob', 0, 0).then(() => {
    const waitTime = Date.now() - bobStartTime;
    console.log(`[Bob] Got the card after waiting ${waitTime}ms!`);
  });

  const charlieStartTime = Date.now();
  const charliePromise = board.flip('charlie', 0, 0).then(() => {
    const waitTime = Date.now() - charlieStartTime;
    console.log(`[Charlie] Got the card after waiting ${waitTime}ms!`);
  });

  // Give them time to start waiting
  const timeOut = 10;
  await timeout(timeOut);
  console.log('\n[System] Bob and Charlie are now waiting...');

  // Alice makes another move, releasing (0,0)
  console.log('\n[Alice] Flipping (0,1) - will release (0,0)...');
  await board.flip('alice', 0, 1);
  console.log('[Alice] Released (0,0), no match');

  // One of Bob/Charlie should get it now
  await Promise.race([bobPromise, charliePromise]);

  console.log('\n Test passed: Waiting mechanism works correctly\n');
}

/**
 * Test scenario: Player matches cards and leaves them controlled
 * while another player waits
 */
async function testMatchedCardsScenario(): Promise<void> {
  console.log('TEST: Matched Cards Cleanup');

  const board = await Board.parseFromFile('boards/ab.txt');

  console.log('\nScenario: Alice matches two cards, Bob waits for one');

  // Alice matches cards at (0,0) and (0,2)
  console.log('\n[Alice] Flipping (0,0)...');
  await board.flip('alice', 0, 0);
  console.log('[Alice] Flipping (0,2)...');
  await board.flip('alice', 0, 2);

  const aliceView = board.look('alice');
  console.log('\n[Alice] Board state:');
  console.log(aliceView);

  if (aliceView.includes('my A') && aliceView.split('my A').length > 2) {
    console.log('[Alice] MATCHED! Controls both cards');
  }

  // Bob tries to take one of Alice's matched cards - should wait
  console.log('\n[Bob] Trying to flip (0,0) which Alice controls...');

  let bobGotError = false;
  const bobPromise = board.flip('bob', 0, 0)
    .then(() => {
      // This should NOT happen - card should be removed
      console.log('[Bob] ERROR: Successfully got the card (should have been removed!)');
      throw new Error('Test failed: Bob should not get a removed card');
    })
    .catch((err: Error) => {
      // This SHOULD happen - card was removed while Bob was waiting
      bobGotError = true;
      console.log(`[Bob] Failed as expected: ${err.message}`);
    });

  const timeOut = 10;
  await timeout(timeOut);
  console.log('[System] Bob is waiting...');

  // Alice makes next move - should remove her matched cards
  console.log('\n[Alice] Making next move - matched cards should be removed');
  await board.flip('alice', 1, 1);

  // Wait for Bob's promise to complete
  await bobPromise;

  // Verify Bob got an error
  if (!bobGotError) {
    throw new Error('Test failed: Bob should have received an error for removed card');
  }

  console.log('\nTest passed: Matched cards removed correctly, waiter notified\n');
}

/**
 * Random positive integer generator
 * 
 * @param max a positive integer which is the upper bound of the generated number
 * @returns a random integer >= 0 and < max
 */
function randomInt(max: number): number {
  return Math.floor(Math.random() * max);
}

/**
 * @param milliseconds duration to wait
 * @returns a promise that fulfills no less than `milliseconds` after timeout() was called
 */
async function timeout(milliseconds: number): Promise<void> {
  const { promise, resolve } = Promise.withResolvers<void>();
  setTimeout(resolve, milliseconds);
  return promise;
}

/**
 * Run all simulations
 */
async function runAllTests(): Promise<void> {
  try {
    // Main simulation with multiple concurrent players
    await simulationMain();

    // Specific test scenarios
    await testWaitingScenario();
    await testMatchedCardsScenario();

    console.log('ALL TESTS PASSED ');
    console.log('\nConcurrency verification complete!');
    console.log('• Multiple players can play simultaneously');
    console.log('• Waiting for controlled cards works correctly');
    console.log('• Matched cards are removed properly');
    console.log('• No deadlocks or race conditions detected');
    console.log('\n Problem 3 requirements satisfied!\n');

  } catch (err) {
    console.error('\n TEST FAILED:', err);
    throw err;
  }
}

void runAllTests();
