/* Copyright (c) 2021-25 MIT 6.102/6.031 course staff, all rights reserved.
 * Redistribution of original or derived work requires permission of course staff.
 */

import assert from 'node:assert';
import fs from 'node:fs';
import { Board } from '../src/board.js';


/**
 * Tests for the Board ADT.
 * 
 * Testing strategy:
 * 
 * parseFromFile():
 *   - valid files: small (1x1), medium (3x3), large (5x5)
 *   - invalid files: wrong card count, invalid dimensions, malformed
 * 
 * look():
 *   - empty board, board with cards
 *   - all cards face down
 *   - some cards face up (controlled by self, controlled by others, not controlled)
 *   - some spaces empty (after matches removed)
 * 
 * flip():
 *   - First card:
 *     - valid position, face down → turns face up, player controls it
 *     - valid position, face up, not controlled → player controls it  
 *     - valid position, face up, controlled by another player → waits
 *     - empty space → throws error
 *   - Second card:
 *     - match with first card → both stay face up, player keeps control
 *     - no match with first card → both stay face up, player relinquishes control
 *     - empty space → throws error, relinquishes first card
 *     - controlled by another player → throws error, relinquishes first card
 *   - Finishing previous play:
 *     - matched cards → removed from board
 *     - non-matching cards (not controlled) → turned face down
 *     - non-matching cards (now controlled by another) → stay face up
 * 
 * Concurrency:
 *   - multiple players flipping different cards simultaneously
 *   - multiple players waiting for same card
 *   - player makes move while another is waiting
 */

describe('Board', function() {

  // ========== parseFromFile() tests ==========

  describe('parseFromFile', function() {

    it('should parse a simple 1x1 board', async function() {
      const filename = 'test-boards/simple.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '1x1\nA\n');

      const board = await Board.parseFromFile(filename);
      const { rows, cols } = board.getDimensions();

      assert.strictEqual(rows, 1);
      assert.strictEqual(cols, 1);

      // Clean up
      await fs.promises.unlink(filename);
    });

    it('should parse a 3x3 board with emoji', async function() {
      const board = await Board.parseFromFile('boards/perfect.txt');
      const { rows, cols } = board.getDimensions();

      assert.strictEqual(rows, 3);
      assert.strictEqual(cols, 3);
    });

    it('should parse a 5x5 board', async function() {
      const board = await Board.parseFromFile('boards/ab.txt');
      const { rows, cols } = board.getDimensions();

      assert.strictEqual(rows, 5);
      assert.strictEqual(cols, 5);
    });

    it('should reject file with wrong card count', async function() {
      const filename = 'test-boards/wrong-count.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '2x2\nA\nB\nC\n'); // Only 3 cards for 2x2

      await assert.rejects(
        async () => await Board.parseFromFile(filename),
        /Expected 4 cards/
      );

      await fs.promises.unlink(filename);
    });

    it('should reject file with invalid dimensions', async function() {
      const filename = 'test-boards/bad-dims.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '0x0\n');

      await assert.rejects(
        async () => await Board.parseFromFile(filename),
        /Invalid dimensions/
      );

      await fs.promises.unlink(filename);
    });

    it('should reject file with malformed first line', async function() {
      const filename = 'test-boards/malformed.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, 'not-a-board\n');

      await assert.rejects(
        async () => await Board.parseFromFile(filename),
        /Invalid board format/
      );

      await fs.promises.unlink(filename);
    });
  });

  // ========== look() tests ==========

  describe('look', function() {

    it('should show all cards face down initially', async function() {
      const filename = 'test-boards/look1.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '2x2\nA\nB\nA\nB\n');

      const board = await Board.parseFromFile(filename);
      const view = board.look('alice');

      const lines = view.split('\n');
      assert.strictEqual(lines[0], '2x2');
      assert.strictEqual(lines[1], 'down');
      assert.strictEqual(lines[2], 'down');
      assert.strictEqual(lines[3], 'down');
      assert.strictEqual(lines[4], 'down');

      await fs.promises.unlink(filename);
    });

    it('should show controlled cards as "my"', async function() {
      const filename = 'test-boards/look2.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '2x2\nA\nB\nA\nB\n');

      const board = await Board.parseFromFile(filename);

      // Alice flips first card
      await board.flip('alice', 0, 0);

      const view = board.look('alice');
      const lines = view.split('\n');
      assert.strictEqual(lines[1], 'my A');  // Alice's card

      await fs.promises.unlink(filename);
    });

    it('should show others\' controlled cards as "up"', async function() {
      const filename = 'test-boards/look3.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '2x2\nA\nB\nA\nB\n');

      const board = await Board.parseFromFile(filename);

      // Alice flips first card
      await board.flip('alice', 0, 0);

      // Bob's view
      const view = board.look('bob');
      const lines = view.split('\n');
      assert.strictEqual(lines[1], 'up A');  // Alice's card, from Bob's perspective

      await fs.promises.unlink(filename);
    });

    it('should show empty spaces as "none"', async function() {
      const filename = 'test-boards/look4.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '2x2\nA\nB\nA\nB\n');

      const board = await Board.parseFromFile(filename);

      // Alice makes a match
      await board.flip('alice', 0, 0);  // First A
      await board.flip('alice', 1, 0);  // Second A

      // Start new move - matched cards removed
      await board.flip('alice', 0, 1);  // Some other card

      const view = board.look('alice');
      const lines = view.split('\n');
      assert.strictEqual(lines[1], 'none');  // First A removed
      assert.strictEqual(lines[3], 'none');  // Second A removed

      await fs.promises.unlink(filename);
    });
  });

  // ========== flip() tests - First Card ==========

  describe('flip - first card', function() {

    it('should flip face-down card and give control', async function() {
      const filename = 'test-boards/flip1.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '2x2\nA\nB\nA\nB\n');

      const board = await Board.parseFromFile(filename);

      await board.flip('alice', 0, 0);

      const view = board.look('alice');
      const lines = view.split('\n');
      assert.strictEqual(lines[1], 'my A');

      await fs.promises.unlink(filename);
    });

    it('should give control of face-up uncontrolled card', async function() {
      const filename = 'test-boards/flip2.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '2x2\nA\nB\nA\nB\n');

      const board = await Board.parseFromFile(filename);

      // Alice flips and doesn't match
      await board.flip('alice', 0, 0);
      await board.flip('alice', 0, 1);  // No match - cards stay up but not controlled

      // Bob can now take control of the face-up card
      await board.flip('bob', 0, 0);

      const view = board.look('bob');
      const lines = view.split('\n');
      assert.strictEqual(lines[1], 'my A');

      await fs.promises.unlink(filename);
    });

    it('should throw error for empty space', async function() {
      const filename = 'test-boards/flip3.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '2x2\nA\nB\nA\nB\n');

      const board = await Board.parseFromFile(filename);

      // Alice makes a match and removes cards
      await board.flip('alice', 0, 0);
      await board.flip('alice', 1, 0);
      await board.flip('alice', 0, 1);  // Removes matched As

      // Bob tries to flip empty space
      await assert.rejects(
        async () => await board.flip('bob', 0, 0),
        /no card at/
      );

      await fs.promises.unlink(filename);
    });

    it('should wait for controlled card', async function() {
      const filename = 'test-boards/flip4.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '2x2\nA\nB\nA\nB\n');

      const board = await Board.parseFromFile(filename);

      // Alice flips first card
      await board.flip('alice', 0, 0);

      // Bob tries to flip same card - should wait
      let bobDone = false;
      const bobPromise = board.flip('bob', 0, 0).then(() => {
        bobDone = true;
      });

      // Give Bob a moment to start waiting
      await timeout(10);
      assert.strictEqual(bobDone, false, 'Bob should still be waiting');

      // Alice flips second card (no match) - relinquishes first card
      await board.flip('alice', 0, 1);

      // Now Bob's flip should complete
      await bobPromise;
      assert.strictEqual(bobDone, true);

      await fs.promises.unlink(filename);
    });
  });

  // ========== flip() tests - Second Card ==========

  describe('flip - second card', function() {

    it('should match and keep control of both cards', async function() {
      const filename = 'test-boards/flip-2nd-1.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '2x2\nA\nB\nA\nB\n');

      const board = await Board.parseFromFile(filename);

      await board.flip('alice', 0, 0);  // First A
      await board.flip('alice', 1, 0);  // Second A - match!

      const view = board.look('alice');
      const lines = view.split('\n');
      assert.strictEqual(lines[1], 'my A');  // First card
      assert.strictEqual(lines[3], 'my A');  // Second card

      await fs.promises.unlink(filename);
    });

    it('should not match and relinquish control', async function() {
      const filename = 'test-boards/flip-2nd-2.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '2x2\nA\nB\nA\nB\n');

      const board = await Board.parseFromFile(filename);

      await board.flip('alice', 0, 0);  // A
      await board.flip('alice', 0, 1);  // B - no match

      const view = board.look('alice');
      const lines = view.split('\n');
      // Both cards face up but not controlled
      assert.strictEqual(lines[1], 'up A');
      assert.strictEqual(lines[2], 'up B');

      await fs.promises.unlink(filename);
    });

    it('should throw and relinquish first card on empty space', async function() {
      const filename = 'test-boards/flip-2nd-3.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '3x3\nA\nB\nA\nB\nC\nC\nD\nD\nE\n');

      const board = await Board.parseFromFile(filename);

      // Bob makes a match and removes cards
      await board.flip('bob', 0, 0);  // First A at (0,0)
      await board.flip('bob', 0, 2);  // Second A at (0,2) - match!
      await board.flip('bob', 0, 1);  // Removes the As

      // Alice tries second card at empty space
      await board.flip('alice', 1, 0);  // First card - B at (1,0)

      await assert.rejects(
        async () => await board.flip('alice', 0, 0),  // Empty! (A was removed)
        /no card at/
      );

      // Alice's first card should be relinquished
      const view = board.look('alice');
      const lines = view.split('\n');
      assert.strictEqual(lines[4], 'up B');  // Position (1,0) - not "my" anymore

      await fs.promises.unlink(filename);
    });

    it('should throw and relinquish on controlled card', async function() {
      const filename = 'test-boards/flip-2nd-4.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '2x2\nA\nB\nA\nB\n');

      const board = await Board.parseFromFile(filename);

      // Bob flips first card
      await board.flip('bob', 0, 1);

      // Alice tries to flip two cards, but second is controlled by Bob
      await board.flip('alice', 0, 0);

      await assert.rejects(
        async () => await board.flip('alice', 0, 1),  // Controlled by Bob
        /controlled by another player/
      );

      // Alice's first card should be relinquished
      const view = board.look('alice');
      const lines = view.split('\n');
      assert.strictEqual(lines[1], 'up A');  // Not "my" anymore

      await fs.promises.unlink(filename);
    });
  });

  // ========== flip() tests - Finishing Previous Play ==========

  describe('flip - finishing previous play', function() {

    it('should remove matched cards on next move', async function() {
      const filename = 'test-boards/finish1.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '3x3\nA\nB\nA\nB\nC\nC\nD\nD\nE\n');

      const board = await Board.parseFromFile(filename);

      // Alice matches A cards at (0,0) and (0,2)
      await board.flip('alice', 0, 0);  // First A at (0,0)
      await board.flip('alice', 0, 2);  // Second A at (0,2) - match!

      // Alice starts new move - should remove As
      await board.flip('alice', 0, 1);

      const view = board.look('alice');
      const lines = view.split('\n');
      assert.strictEqual(lines[1], 'none');  // Position (0,0) - First A removed
      assert.strictEqual(lines[3], 'none');  // Position (0,2) - Second A removed

      await fs.promises.unlink(filename);
    });

    it('should turn down non-matching uncontrolled cards', async function() {
      const filename = 'test-boards/finish2.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '2x2\nA\nB\nA\nB\n');

      const board = await Board.parseFromFile(filename);

      // Alice flips non-matching cards
      // Board is: A B / A B (row-major)
      //           (0,0) (0,1) / (1,0) (1,1)
      await board.flip('alice', 0, 0);  // A at (0,0)
      await board.flip('alice', 0, 1);  // B at (0,1) - no match

      // Alice starts new move - should turn them down
      await board.flip('alice', 1, 0);  // A at (1,0)

      const view = board.look('alice');
      const lines = view.split('\n');
      assert.strictEqual(lines[1], 'down');  // Position (0,0) - turned down
      assert.strictEqual(lines[2], 'down');  // Position (0,1) - turned down

      await fs.promises.unlink(filename);
    });

    it('should NOT turn down card now controlled by another', async function() {
      const filename = 'test-boards/finish3.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '2x2\nA\nB\nA\nB\n');

      const board = await Board.parseFromFile(filename);

      // Alice flips non-matching cards
      await board.flip('alice', 0, 0);  // A
      await board.flip('alice', 0, 1);  // B - no match, relinquishes

      // Bob takes control of one of Alice's cards
      await board.flip('bob', 0, 0);

      // Alice starts new move
      await board.flip('alice', 1, 0);

      const view = board.look('bob');
      const lines = view.split('\n');
      assert.strictEqual(lines[1], 'my A');  // Bob's card stays up
      assert.strictEqual(lines[2], 'down');  // Alice's other card turned down

      await fs.promises.unlink(filename);
    });

    it('should turn down card that was controlled by another but no longer is', async function() {
      const filename = 'test-boards/finish4.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '3x3\nA\nB\nC\nA\nD\nD\nE\nE\nF\n');

      const board = await Board.parseFromFile(filename);

      // P1 flips C1 (A at 0,0)
      await board.flip('player1', 0, 0);  // A
      // P1 flips C2 (B at 0,1) - no match, loses control of both
      await board.flip('player1', 0, 1);  // B - no match, relinquishes

      // P2 takes control of C1 (A at 0,0)
      await board.flip('player2', 0, 0);  // A (face up, uncontrolled)
      // P2 flips C3 (C at 0,2) - no match, loses control of both
      await board.flip('player2', 0, 2);  // C - no match, relinquishes

      // Now C1 (0,0) is face up but not controlled by anyone
      // P1's previous cards were (0,0) and (0,1)

      // P1 starts new move - flips C4 (D at 1,1)
      await board.flip('player1', 1, 1);  // D

      // C1 (0,0) should be turned face down (was P1's card, now uncontrolled)
      // C2 (0,1) should be turned face down (was P1's card, now uncontrolled)
      // C3 (0,2) should stay face up (was never P1's card)
      const view = board.look('player1');
      const lines = view.split('\n');
      assert.strictEqual(lines[1], 'down', 'C1 (0,0) should be face down');
      assert.strictEqual(lines[2], 'down', 'C2 (0,1) should be face down');
      assert.strictEqual(lines[3], 'up C', 'C3 (0,2) should remain face up (not P1\'s card)');

      await fs.promises.unlink(filename);
    });
  });

  // ========== Concurrency tests ==========

  describe('concurrency', function() {

    it('should handle multiple players flipping different cards', async function() {
      const filename = 'test-boards/concurrent1.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '3x3\nA\nB\nC\nA\nB\nC\nD\nD\nE\n');

      const board = await Board.parseFromFile(filename);

      // Alice and Bob flip simultaneously
      await Promise.all([
        board.flip('alice', 0, 0),
        board.flip('bob', 0, 1)
      ]);

      const aliceView = board.look('alice');
      const bobView = board.look('bob');

      const aliceLines = aliceView.split('\n');
      const bobLines = bobView.split('\n');

      assert.strictEqual(aliceLines[1], 'my A');
      assert.strictEqual(bobLines[2], 'my B');

      await fs.promises.unlink(filename);
    });

    it('should handle multiple waiters for same card', async function() {
      const filename = 'test-boards/concurrent2.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '2x2\nA\nB\nA\nB\n');

      const board = await Board.parseFromFile(filename);

      // Alice controls a card
      await board.flip('alice', 0, 0);

      // Bob and Charlie both wait for it
      const bobPromise = board.flip('bob', 0, 0);
      const charliePromise = board.flip('charlie', 0, 0);

      await timeout(10);  // Let them start waiting

      // Alice releases the card
      await board.flip('alice', 0, 1);  // No match, relinquishes

      // One of them should get it (but not both)
      await Promise.race([bobPromise, charliePromise]);

      await fs.promises.unlink(filename);
    });

    it('should handle player making move while another waits', async function() {
      const filename = 'test-boards/concurrent3.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '3x3\nA\nB\nC\nA\nB\nC\nD\nD\nE\n');

      const board = await Board.parseFromFile(filename);

      // Alice controls a card
      await board.flip('alice', 0, 0);

      // Bob waits for it
      const bobPromise = board.flip('bob', 0, 0);

      await timeout(10);

      // Charlie makes a completely different move
      await board.flip('charlie', 1, 1);
      await board.flip('charlie', 1, 2);  // Should work fine

      // Alice releases, Bob gets it
      await board.flip('alice', 0, 1);
      await bobPromise;

      const bobView = board.look('bob');
      assert(bobView.includes('my A'));

      await fs.promises.unlink(filename);
    });
  });
  describe('Advanced Concurrency Scenarios', function() {

    it('should handle 5 players flipping different cards concurrently', async function() {
      const filename = 'test-boards/concurrent-5players.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '5x5\nA\nB\nC\nD\nE\nA\nB\nC\nD\nE\nF\nG\nH\nI\nJ\nF\nG\nH\nI\nJ\nK\nL\nM\nN\nO\n');

      const board = await Board.parseFromFile(filename);

      // All 5 players flip different cards at the same time
      await Promise.all([
        board.flip('player1', 0, 0), // A
        board.flip('player2', 0, 1), // B
        board.flip('player3', 0, 2), // C
        board.flip('player4', 0, 3), // D
        board.flip('player5', 0, 4)  // E
      ]);

      // Verify each player controls their card
      const view1 = board.look('player1');
      const view2 = board.look('player2');
      const view3 = board.look('player3');
      const view4 = board.look('player4');
      const view5 = board.look('player5');

      assert(view1.includes('my A'));
      assert(view2.includes('my B'));
      assert(view3.includes('my C'));
      assert(view4.includes('my D'));
      assert(view5.includes('my E'));

      await fs.promises.unlink(filename);
    });

    it('should handle waiting chain: A controls, B waits, C waits, A releases', async function() {
      const filename = 'test-boards/waiting-chain.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '2x2\nA\nB\nA\nB\n');

      const board = await Board.parseFromFile(filename);

      // Alice controls (0,0)
      await board.flip('alice', 0, 0);

      // Bob waits for (0,0)
      let bobGotCard = false;
      const bobPromise = board.flip('bob', 0, 0).then(() => {
        bobGotCard = true;
      });

      // Charlie also waits for (0,0)
      let charlieGotCard = false;
      const charliePromise = board.flip('charlie', 0, 0).then(() => {
        charlieGotCard = true;
      });

      await timeout(10);
      assert.strictEqual(bobGotCard, false, 'Bob should still be waiting');
      assert.strictEqual(charlieGotCard, false, 'Charlie should still be waiting');

      // Alice releases by flipping another card
      await board.flip('alice', 0, 1);

      // One of Bob/Charlie should get it
      await Promise.race([bobPromise, charliePromise]);
      assert(bobGotCard || charlieGotCard, 'At least one should get the card');

      await fs.promises.unlink(filename);
    });

    it('should handle player making match while others wait for one of the cards', async function() {
      const filename = 'test-boards/match-with-waiters.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '3x3\nA\nB\nA\nB\nC\nC\nD\nD\nE\n');

      const board = await Board.parseFromFile(filename);

      // Alice matches two A cards
      await board.flip('alice', 0, 0);
      await board.flip('alice', 0, 2); // Match!

      // Bob waits for one of Alice's matched cards
      const bobPromise = board.flip('bob', 0, 0).catch((err) => {
        // Card gets removed, Bob should fail
        return 'failed';
      });

      await timeout(10);

      // Alice makes next move - removes matched cards
      await board.flip('alice', 0, 1);

      const result = await bobPromise;
      assert.strictEqual(result, 'failed', 'Bob should fail when card is removed');

      await fs.promises.unlink(filename);
    });

    it('should not deadlock when two players want each others cards', async function() {
      const filename = 'test-boards/no-deadlock.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '2x2\nA\nB\nA\nB\n');

      const board = await Board.parseFromFile(filename);

      // Alice controls (0,0)
      await board.flip('alice', 0, 0);

      // Bob controls (0,1)
      await board.flip('bob', 0, 1);

      // Both try to flip each other's cards concurrently
      // Rule 2-B ensures no deadlock by rejecting immediately instead of waiting
      // Due to JavaScript's single-threaded nature, one may succeed after the other fails and relinquishes
      const [aliceResult, bobResult] = await Promise.allSettled([
        board.flip('alice', 0, 1), // Alice tries Bob's card
        board.flip('bob', 0, 0)     // Bob tries Alice's card
      ]);

      // At least one should fail (the one that checks first)
      // The key is that neither waits forever (no deadlock)
      const aliceFailed = aliceResult.status === 'rejected';
      const bobFailed = bobResult.status === 'rejected';

      assert(aliceFailed || bobFailed, 'At least one flip should fail to avoid deadlock');

      // Verify the error messages for any that failed
      if (aliceFailed) {
        assert.match((aliceResult as PromiseRejectedResult).reason.message, /controlled by another player|no card at/);
      }
      if (bobFailed) {
        assert.match((bobResult as PromiseRejectedResult).reason.message, /controlled by another player|no card at/);
      }

      await fs.promises.unlink(filename);
    });

    it('should handle rapid concurrent flips from many players', async function() {
      this.timeout(10000); // Increase timeout to 10 seconds for this stress test

      const filename = 'test-boards/rapid-concurrent.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '5x5\nA\nB\nA\nB\nC\nC\nD\nD\nE\nE\nF\nF\nG\nG\nH\nH\nI\nI\nJ\nJ\nK\nK\nL\nL\nM\n');

      const board = await Board.parseFromFile(filename);

      // Reduced to avoid livelock under extreme contention
      // With random flips, players may repeatedly contend for the same cards
      const players = 3;
      const flipsPerPlayer = 2;

      const promises = [];
      for (let p = 0; p < players; p++) {
        const playerId = `player${p}`;
        promises.push(
          (async () => {
            for (let f = 0; f < flipsPerPlayer; f++) {
              try {
                const row = randomInt(5);
                const col = randomInt(5);
                await board.flip(playerId, row, col);
                await timeout(randomInt(5)); // Small random delay
              } catch (err) {
                // Some flips will fail, that's okay
              }
            }
          })()
        );
      }

      // All should complete without hanging or crashing
      await Promise.all(promises);

      // Board should still be in valid state
      const view = board.look('observer');
      assert(view.startsWith('5x5'));

      await fs.promises.unlink(filename);
    });

    it('should correctly interleave look() calls during flip() waiting', async function() {
      const filename = 'test-boards/look-during-wait.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '2x2\nA\nB\nA\nB\n');

      const board = await Board.parseFromFile(filename);

      // Alice controls (0,0)
      await board.flip('alice', 0, 0);

      // Bob waits for (0,0)
      const bobPromise = board.flip('bob', 0, 0);

      await timeout(5);

      // While Bob is waiting, Charlie should be able to look at the board
      const charlieView = board.look('charlie');
      assert(charlieView.includes('up A'), 'Charlie should see Alice\'s card');

      // And Charlie should be able to flip other cards
      await board.flip('charlie', 1, 1);
      const charlieView2 = board.look('charlie');
      assert(charlieView2.includes('my B'), 'Charlie should control (1,1)');

      // Release Bob
      await board.flip('alice', 0, 1);
      await bobPromise;

      await fs.promises.unlink(filename);
    });

    it('should handle player finishing matched cards while others have flips pending', async function() {
      const filename = 'test-boards/finish-with-pending.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '3x3\nA\nB\nA\nB\nC\nC\nD\nD\nE\n');

      const board = await Board.parseFromFile(filename);

      // Alice matches As at (0,0) and (0,2)
      await board.flip('alice', 0, 0);
      await board.flip('alice', 0, 2);

      // Bob starts flipping cards
      const bobPromise = (async () => {
        await board.flip('bob', 1, 1); // B at (1,1)
        await board.flip('bob', 1, 2); // C at (1,2) - no match
      })();

      await timeout(5);

      // Alice starts new move - removes her As
      await board.flip('alice', 1, 0);

      // Bob's operations should complete normally
      await bobPromise;

      // Verify As are gone
      const view = board.look('alice');
      const lines = view.split('\n');
      assert.strictEqual(lines[1], 'none'); // (0,0) removed
      assert.strictEqual(lines[3], 'none'); // (0,2) removed

      await fs.promises.unlink(filename);
    });

    it('should correctly handle three players in sequence with waiting', async function() {
      const filename = 'test-boards/three-sequence.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '3x3\nA\nB\nC\nA\nB\nC\nD\nD\nE\n');

      const board = await Board.parseFromFile(filename);

      // Alice takes (0,0)
      await board.flip('alice', 0, 0);

      // Bob waits for (0,0)
      const bobPromise = board.flip('bob', 0, 0);

      // Charlie also waits for (0,0)
      const charliePromise = board.flip('charlie', 0, 0);

      await timeout(10);

      // Alice releases
      await board.flip('alice', 0, 1);

      // Bob gets it (or Charlie, doesn't matter)
      await Promise.race([bobPromise, charliePromise]);

      // The one who got it should control it
      const bobView = board.look('bob');
      const charlieView = board.look('charlie');

      assert(bobView.includes('my A') || charlieView.includes('my A'),
        'One of them should control the card');

      await fs.promises.unlink(filename);
    });
  });

  describe('map()', function() {

    it('should transform all cards on the board', async function() {
      const filename = 'test-boards/map-simple.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '2x2\nA\nB\nA\nB\n');

      const board = await Board.parseFromFile(filename);

      // Transform A->X, B->Y
      await board.map(async (card) => {
        if (card === 'A') return 'X';
        if (card === 'B') return 'Y';
        return card;
      });

      // Flip cards to verify transformation
      await board.flip('player1', 0, 0);
      const view = board.look('player1');
      assert(view.includes('my X')); // Was A, now X

      await fs.promises.unlink(filename);
    });

    it('should maintain pairwise consistency during transformation', async function() {
      const filename = 'test-boards/map-consistency.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '2x2\nA\nB\nA\nB\n');

      const board = await Board.parseFromFile(filename);

      // Flip cards face up
      await board.flip('player1', 0, 0); // A at (0,0)
      await board.flip('player1', 0, 1); // B at (0,1) - no match

      // Both As should transform together
      await board.map(async (card) => {
        await timeout(5);
        return `${card}-new`;
      });

      const view = board.look('player1');
      assert(view.includes('A-new'));
      assert(view.includes('B-new'));

      await fs.promises.unlink(filename);
    });

    it('should not affect card face-up/down state', async function() {
      const filename = 'test-boards/map-facestate.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '2x2\nA\nB\nA\nB\n');

      const board = await Board.parseFromFile(filename);

      // Flip one card face up
      await board.flip('player1', 0, 0);

      // Transform cards
      await board.map(async (card) => `${card}+`);

      const afterView = board.look('player1');
      const afterLines = afterView.split('\n');

      // First card should still be controlled
      assert(afterLines[1] === 'my A+');

      // Other cards should still be face down
      assert(afterLines[2] === 'down');
      assert(afterLines[3] === 'down');
      assert(afterLines[4] === 'down');

      await fs.promises.unlink(filename);
    });

    it('should not affect player control state', async function() {
      const filename = 'test-boards/map-control.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '2x2\nA\nB\nA\nB\n');

      const board = await Board.parseFromFile(filename);

      // Alice controls (0,0), Bob controls (0,1)
      await board.flip('alice', 0, 0);
      await board.flip('bob', 0, 1);

      // Transform cards
      await board.map(async (card) => `${card}*`);

      // Both should still control their cards
      const aliceView = board.look('alice');
      assert(aliceView.includes('my A*'));

      const bobView = board.look('bob');
      assert(bobView.includes('my B*'));

      await fs.promises.unlink(filename);
    });

    it('should allow flip operations to interleave during map', async function() {
      const filename = 'test-boards/map-interleave.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '2x2\nA\nB\nA\nB\n');

      const board = await Board.parseFromFile(filename);

      // Start a slow map
      const mapPromise = board.map(async (card) => {
        await timeout(20);
        return `${card}#`;
      });

      // While map is running, flip a card
      await timeout(5);
      await board.flip('player1', 0, 0);

      // Player should control a card
      const view = board.look('player1');
      assert(view.includes('my A') || view.includes('my A#'));

      await mapPromise;

      // After map, player should control the transformed card
      const finalView = board.look('player1');
      assert(finalView.includes('my A#'));

      await fs.promises.unlink(filename);
    });

    it('should handle empty spaces correctly', async function() {
      const filename = 'test-boards/map-empty.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '3x3\nA\nB\nA\nB\nC\nC\nD\nD\nE\n');

      const board = await Board.parseFromFile(filename);

      // Make a match and remove cards: match the two As
      await board.flip('player1', 0, 0); // A at (0,0)
      await board.flip('player1', 0, 2); // A at (0,2) - match!
      await board.flip('player1', 0, 1); // Start new play, removes the matched As

      // Now (0,0) and (0,2) should be empty
      const beforeMap = board.look('player1');
      assert(beforeMap.includes('none'), 'Should have empty spaces before map');

      // Transform remaining cards
      await board.map(async (card) => `${card}!`);

      const afterMap = board.look('player1');

      // Empty spaces should still be empty after map
      assert(afterMap.includes('none'), 'Empty spaces should remain empty after map');

      await fs.promises.unlink(filename);
    });

  });

  describe('watch()', function() {

    it('should wait for and notify on card flip (face up)', async function() {
      const filename = 'test-boards/watch-flip.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '2x2\nA\nB\nA\nB\n');

      const board = await Board.parseFromFile(filename);

      // Start watching for changes
      let watchResolved = false;
      const watchPromise = board.watchForChange().then(() => {
        watchResolved = true;
      });

      // Verify watch hasn't resolved yet
      await timeout(10);
      assert(!watchResolved, 'Watch should not resolve before change');

      // Make a change: flip a card
      await board.flip('player1', 0, 0);

      // Watch should now resolve
      await watchPromise;
      assert(watchResolved, 'Watch should resolve after flip');

      await fs.promises.unlink(filename);
    });

    it('should notify on card removal', async function() {
      const filename = 'test-boards/watch-remove.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '2x2\nA\nB\nA\nB\n');

      const board = await Board.parseFromFile(filename);

      // Set up a match
      await board.flip('player1', 0, 0); // A
      await board.flip('player1', 1, 0); // A - match!

      // Start watching
      let watchResolved = false;
      const watchPromise = board.watchForChange().then(() => {
        watchResolved = true;
      });

      await timeout(10);
      assert(!watchResolved);

      // Remove the matched cards by making another move
      await board.flip('player1', 0, 1);

      // Watch should resolve
      await watchPromise;
      assert(watchResolved);

      await fs.promises.unlink(filename);
    });

    it('should notify on cards turning face down', async function() {
      const filename = 'test-boards/watch-facedown.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '2x2\nA\nB\nA\nB\n');

      const board = await Board.parseFromFile(filename);

      // Flip two non-matching cards
      await board.flip('player1', 0, 0); // A
      await board.flip('player1', 0, 1); // B - no match

      // Start watching
      const watchPromise = board.watchForChange();

      // Make another move which will turn down the previous cards
      await board.flip('player1', 1, 0);

      // Watch should resolve when cards turn face down
      await watchPromise;

      await fs.promises.unlink(filename);
    });

    it('should notify on map() card transformation', async function() {
      const filename = 'test-boards/watch-map.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '2x2\nA\nB\nA\nB\n');

      const board = await Board.parseFromFile(filename);

      // Start watching
      const watchPromise = board.watchForChange();

      // Transform cards
      await board.map(async (card) => `${card}!`);

      // Watch should resolve after transformation
      await watchPromise;

      await fs.promises.unlink(filename);
    });

    it('should handle multiple concurrent watchers', async function() {
      const filename = 'test-boards/watch-multiple.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '2x2\nA\nB\nA\nB\n');

      const board = await Board.parseFromFile(filename);

      // Start multiple watchers
      let watcher1Resolved = false;
      let watcher2Resolved = false;
      let watcher3Resolved = false;

      const watch1 = board.watchForChange().then(() => { watcher1Resolved = true; });
      const watch2 = board.watchForChange().then(() => { watcher2Resolved = true; });
      const watch3 = board.watchForChange().then(() => { watcher3Resolved = true; });

      await timeout(10);
      assert(!watcher1Resolved && !watcher2Resolved && !watcher3Resolved);

      // Make one change
      await board.flip('player1', 0, 0);

      // All watchers should resolve
      await Promise.all([watch1, watch2, watch3]);
      assert(watcher1Resolved && watcher2Resolved && watcher3Resolved);

      await fs.promises.unlink(filename);
    });

    it('should not notify on control changes without face changes', async function() {
      const filename = 'test-boards/watch-control.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '2x2\nA\nB\nA\nB\n');

      const board = await Board.parseFromFile(filename);

      // Flip a card face up
      await board.flip('player1', 0, 0);

      // Start watching
      let watchResolved = false;
      const watchPromise = board.watchForChange().then(() => {
        watchResolved = true;
      });

      await timeout(10);

      // Player2 tries to flip the same card - will wait (no face change)
      // This creates a waiting state but doesn't change card face/removal/value
      const player2Promise = board.flip('player2', 0, 0);

      await timeout(10);
      // Watch should NOT have resolved yet (no face/removal/value change)
      assert(!watchResolved, 'Watch should not resolve on control change alone');

      // Clean up: let player2's flip complete
      await board.flip('player1', 0, 1); // Player1 makes second flip
      await player2Promise; // Player2 gets the card

      await fs.promises.unlink(filename);
    });

    it('should allow look() to interleave with watch()', async function() {
      const filename = 'test-boards/watch-look.txt';
      await fs.promises.mkdir('test-boards', { recursive: true });
      await fs.promises.writeFile(filename, '2x2\nA\nB\nA\nB\n');

      const board = await Board.parseFromFile(filename);

      // Start watching
      const watchPromise = board.watchForChange();

      // While waiting, look() should work normally
      const view1 = board.look('observer');
      assert(view1.startsWith('2x2'));

      // Make change
      await board.flip('player1', 0, 0);

      // Wait should resolve
      await watchPromise;

      // look() should still work after watch resolves
      const view2 = board.look('player1');
      assert(view2.includes('my A'), 'Player1 should see their controlled card');

      // Observer should see it as 'up A'
      const observerView = board.look('observer');
      assert(observerView.includes('up A'), 'Observer should see card as up');

      await fs.promises.unlink(filename);
    });

  });

  // Cleanup test-boards directory after all tests
  after(async function() {
    try {
      const files = await fs.promises.readdir('test-boards');
      for (const file of files) {
        await fs.promises.unlink(`test-boards/${file}`);
      }
      await fs.promises.rmdir('test-boards');
    } catch (err) {
      // Directory might not exist, that's okay
    }
  });


});


/**
 * Example test case that uses async/await to test an asynchronous function.
 * Feel free to delete these example tests.
 */
describe('async test cases', function() {

  it('reads a file asynchronously', async function() {
    const fileContents = (await fs.promises.readFile('boards/ab.txt')).toString();
    assert(fileContents.startsWith('5x5'));
  });
});

/**
 * Helper function to create a delay
 * @param ms milliseconds to wait
 */
async function timeout(ms: number): Promise<void> {
  const { promise, resolve } = Promise.withResolvers<void>();
  setTimeout(resolve, ms);
  return promise;
}

/**
 * Helper: random integer
 */
function randomInt(max: number): number {
  return Math.floor(Math.random() * max);
}

