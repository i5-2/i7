#!/usr/bin/env python
#/usr/local/bin/python3
# Set the path to your python3 above

from gtp_connection import GtpConnection
from board_util import GoBoardUtil, EMPTY
from simple_board import SimpleGoBoard

import random
import numpy as np

from pattern_util import PatternUtil
from simple_board import SimpleGoBoard
from mcts import MCTS

def undo(board,move):
    board.board[move]=EMPTY
    board.current_player=GoBoardUtil.opponent(board.current_player)

def play_move(board, move, color):
    board.play_move_gomoku(move, color)

def game_result(board):
    game_end, winner = board.check_game_end_gomoku()
    moves = board.get_empty_points()
    board_full = (len(moves) == 0)
    if game_end:
        #return 1 if winner == board.current_player else -1
        return winner
    if board_full:
        return 'draw'
    return None

def count_at_depth(node, depth, nodesAtDepth):
    if not node._expanded:
        return
    nodesAtDepth[depth] += 1
    for _,child in node._children.items():
        count_at_depth(child, depth+1, nodesAtDepth)

class GomokuSimulationPlayer(object):
    def __init__(self, num_sim, sim_rule, move_filter, in_tree_knowledge, size=7, limit=50, exploration=0.4):
        """
        Player that selects a move based on MCTS from the set of legal moves
        """
        self.name = "Gomoku4"
        self.version = 0.22
        self.komi = 0
        self.MCTS = MCTS()
        self.num_simulation = num_sim
        self.limit = limit
        self.exploration = exploration 
        self.simulation_policy = sim_rule
        self.use_pattern = True
        self.check_selfatari = move_filter
        self.in_tree_knowledge = in_tree_knowledge
        self.parent = None
        self.best_move = None
    
    def reset(self):
        self.MCTS = MCTS()

    def update(self, move):
        self.parent = self.MCTS._root 
        self.MCTS.update_with_move(move)
        self.best_move = move
    
    def get_move(self, board, toplay):
        move = self.MCTS.get_move(board,
                toplay,
                komi=self.komi,
                limit=self.limit,
                check_selfatari=self.check_selfatari,
                use_pattern=self.use_pattern,
                num_simulation = self.num_simulation,
                exploration = self.exploration,
                simulation_policy = self.simulation_policy,
                in_tree_knowledge = self.in_tree_knowledge)
        self.update(move)
        return move

    def get_node_depth(self, root):
        MAX_DEPTH = self.limit
        nodesAtDepth = [0] * MAX_DEPTH
        count_at_depth(root, 0, nodesAtDepth)
        prev_nodes = 1
        return nodesAtDepth
    
    def get_properties(self):
        return dict(
            version=self.version,
            name=self.__class__.__name__,
        )
 
def run():
    """
    start the gtp connection and wait for commands.
    """
    board = SimpleGoBoard(7)
    con = GtpConnection(GomokuSimulationPlayer(2000, "random", False, "None"), board)
    con.start_connection()

if __name__=='__main__':
    run()
