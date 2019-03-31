"""
simple_board.py

Implements a basic Go board with functions to:
- initialize to a given board size
- check if a move is legal
- play a move

The board uses a 1-dimensional representation with padding
"""

import numpy as np
from board_util import GoBoardUtil, BLACK, WHITE, EMPTY, BORDER, \
                       PASS, is_black_white, coord_to_point, where1d, \
                       MAXSIZE, NULLPOINT
import alphabeta
import collections

WINNER_SCORE = 100000

# 1 move win (aka "my turn my win")
winDict = {
    "x.xxx": True,
    "xx.xx": True,
    "xxx.x": True,
    ".xxxx": True,
    "xxxx.": True,

    # must block these, if have none of the above
    "o.ooo": False,
    "oo.oo": False,
    "ooo.o": False,
    ".oooo": False,
    "oooo.": False,
}

# 2 move wins (aka "my turn my win in 2 moves")
# must be blocked if seen
# (MyWin, how many steps back to go)
threatDict = {
    ".x.xx.": (True, 3),
    ".xx.x.": (True, 2),
    ".xxx..": (True, 1),
    "..xxx.": (True, 4),

    # must block these, if have none of the above
    ".o.oo.": (False, 3),
    ".oo.o.": (False, 2),
    ".ooo..": (False, 1),
    "..ooo.": (False, 4),
}

class SimpleGoBoard(object):

    def get_color(self, point):
        return self.board[point]

    def pt(self, row, col):
        return coord_to_point(row, col, self.size)

    def is_legal(self, point, color):
        """
        Check whether it is legal for color to play on point
        """
        assert is_black_white(color)
        # Special cases
        if point == PASS:
            return True
        elif self.board[point] != EMPTY:
            return False
        if point == self.ko_recapture:
            return False
            
        # General case: detect captures, suicide
        opp_color = GoBoardUtil.opponent(color)
        self.board[point] = color
        legal = True
        has_capture = self._detect_captures(point, opp_color)
        if not has_capture and not self._stone_has_liberty(point):
            block = self._block_of(point)
            if not self._has_liberty(block): # suicide
                legal = False
        self.board[point] = EMPTY
        return legal

    def _detect_captures(self, point, opp_color):
        """
        Did move on point capture something?
        """
        for nb in self.neighbors_of_color(point, opp_color):
            if self._detect_capture(nb):
                return True
        return False

    def get_empty_points(self):
        """
        Return:
            The empty points on the board
        """
        return where1d(self.board == EMPTY)

    def __init__(self, size):
        """
        Creates a Go board of given size
        """
        assert 2 <= size <= MAXSIZE
        self.reset(size)

    def reset(self, size):
        """
        Creates a start state, an empty board with the given size
        The board is stored as a one-dimensional array
        See GoBoardUtil.coord_to_point for explanations of the array encoding
        """
        self.size = size
        self.NS = size + 1
        self.WE = 1
        self.ko_recapture = None
        self.current_player = BLACK
        self.maxpoint = size * size + 3 * (size + 1)
        self.board = np.full(self.maxpoint, BORDER, dtype = np.int32)
        self.liberty_of = np.full(self.maxpoint, NULLPOINT, dtype = np.int32)
        self._initialize_empty_points(self.board)
        self._initialize_neighbors()
        self.best_move = None
        self.best_move_score = -1000000

    def copy(self):
        b = SimpleGoBoard(self.size)
        assert b.NS == self.NS
        assert b.WE == self.WE
        b.ko_recapture = self.ko_recapture
        b.current_player = self.current_player
        assert b.maxpoint == self.maxpoint
        b.board = np.copy(self.board)
        return b

    def row_start(self, row):
        assert row >= 1
        assert row <= self.size
        return row * self.NS + 1
        
    def _initialize_empty_points(self, board):
        """
        Fills points on the board with EMPTY
        Argument
        ---------
        board: numpy array, filled with BORDER
        """
        for row in range(1, self.size + 1):
            start = self.row_start(row)
            board[start : start + self.size] = EMPTY

    def _on_board_neighbors(self, point):
        nbs = []
        for nb in self._neighbors(point):
            if self.board[nb] != BORDER:
                nbs.append(nb)
        return nbs
            
    def _initialize_neighbors(self):
        """
        precompute neighbor array.
        For each point on the board, store its list of on-the-board neighbors
        """
        self.neighbors = []
        for point in range(self.maxpoint):
            if self.board[point] == BORDER:
                self.neighbors.append([])
            else:
                self.neighbors.append(self._on_board_neighbors(point))
        
    def is_eye(self, point, color):
        """
        Check if point is a simple eye for color
        """
        if not self._is_surrounded(point, color):
            return False
        # Eye-like shape. Check diagonals to detect false eye
        opp_color = GoBoardUtil.opponent(color)
        false_count = 0
        at_edge = 0
        for d in self._diag_neighbors(point):
            if self.board[d] == BORDER:
                at_edge = 1
            elif self.board[d] == opp_color:
                false_count += 1
        return false_count <= 1 - at_edge # 0 at edge, 1 in center
    
    def _is_surrounded(self, point, color):
        """
        check whether empty point is surrounded by stones of color.
        """
        for nb in self.neighbors[point]:
            nb_color = self.board[nb]
            if nb_color != color:
                return False
        return True

    def _stone_has_liberty(self, stone):
        lib = self.find_neighbor_of_color(stone, EMPTY)
        return lib != None

    def _get_liberty(self, block):
        """
        Find any liberty of the given block.
        Returns None in case there is no liberty.
        block is a numpy boolean array
        """
        for stone in where1d(block):
            lib = self.find_neighbor_of_color(stone, EMPTY)
            if lib != None:
                return lib
        return None

    def _has_liberty(self, block):
        """
        Check if the given block has any liberty.
        Also updates the liberty_of array.
        block is a numpy boolean array
        """
        lib = self._get_liberty(block)
        if lib != None:
            assert self.get_color(lib) == EMPTY
            for stone in where1d(block):
                self.liberty_of[stone] = lib
            return True
        return False

    def _block_of(self, stone):
        """
        Find the block of given stone
        Returns a board of boolean markers which are set for
        all the points in the block 
        """
        marker = np.full(self.maxpoint, False, dtype = bool)
        pointstack = [stone]
        color = self.get_color(stone)
        assert is_black_white(color)
        marker[stone] = True
        while pointstack:
            p = pointstack.pop()
            neighbors = self.neighbors_of_color(p, color)
            for nb in neighbors:
                if not marker[nb]:
                    marker[nb] = True
                    pointstack.append(nb)
        return marker

    def _fast_liberty_check(self, nb_point):
        lib = self.liberty_of[nb_point]
        if lib != NULLPOINT and self.get_color(lib) == EMPTY:
            return True # quick exit, block has a liberty  
        if self._stone_has_liberty(nb_point):
            return True # quick exit, no need to look at whole block
        return False
        
    def _detect_capture(self, nb_point):
        """
        Check whether opponent block on nb_point is captured.
        Returns boolean.
        """
        if self._fast_liberty_check(nb_point):
            return False
        opp_block = self._block_of(nb_point)
        return not self._has_liberty(opp_block)
    
    def _detect_and_process_capture(self, nb_point):
        """
        Check whether opponent block on nb_point is captured.
        If yes, remove the stones.
        Returns the stone if only a single stone was captured,
            and returns None otherwise.
        This result is used in play_move to check for possible ko
        """
        if self._fast_liberty_check(nb_point):
            return None
        opp_block = self._block_of(nb_point)
        if self._has_liberty(opp_block):
            return None
        captures = list(where1d(opp_block))
        self.board[captures] = EMPTY
        self.liberty_of[captures] = NULLPOINT
        single_capture = None 
        if len(captures) == 1:
            single_capture = nb_point
        return single_capture

    def play_move(self, point, color):
        """
        Play a move of color on point
        Returns boolean: whether move was legal
        """
        assert is_black_white(color)
        # Special cases
        if point == PASS:
            self.ko_recapture = None
            self.current_player = GoBoardUtil.opponent(color)
            return True
        elif self.board[point] != EMPTY:
            return False
        if point == self.ko_recapture:
            return False
            
        # General case: deal with captures, suicide, and next ko point
        opp_color = GoBoardUtil.opponent(color)
        in_enemy_eye = self._is_surrounded(point, opp_color)
        self.board[point] = color
        single_captures = []
        neighbors = self.neighbors[point]
        for nb in neighbors:
            if self.board[nb] == opp_color:
                single_capture = self._detect_and_process_capture(nb)
                if single_capture != None:
                    single_captures.append(single_capture)
        if not self._stone_has_liberty(point):
            # check suicide of whole block
            block = self._block_of(point)
            if not self._has_liberty(block): # undo suicide move
                self.board[point] = EMPTY
                return False
        self.ko_recapture = None
        if in_enemy_eye and len(single_captures) == 1:
            self.ko_recapture = single_captures[0]
        self.current_player = GoBoardUtil.opponent(color)
        return True

    def neighbors_of_color(self, point, color):
        """ List of neighbors of point of given color """
        nbc = []
        for nb in self.neighbors[point]:
            if self.get_color(nb) == color:
                nbc.append(nb)
        return nbc
        
    def find_neighbor_of_color(self, point, color):
        """ Return one neighbor of point of given color, or None """
        for nb in self.neighbors[point]:
            if self.get_color(nb) == color:
                return nb
        return None
        
    def _neighbors(self, point):
        """ List of all four neighbors of the point """
        return [point - 1, point + 1, point - self.NS, point + self.NS]

    def _diag_neighbors(self, point):
        """ List of all four diagonal neighbors of point """
        return [point - self.NS - 1, 
                point - self.NS + 1, 
                point + self.NS - 1, 
                point + self.NS + 1]
    
    def _point_to_coord(self, point):
        """
        Transform point index to row, col.
        
        Arguments
        ---------
        point
        
        Returns
        -------
        x , y : int
        coordination of the board  1<= x <=size, 1<= y <=size .
        """
        if point is None:
            return 'pass'
        row, col = divmod(point, self.NS)
        return row, col

    def is_legal_gomoku(self, point, color):
        """
            Check whether it is legal for color to play on point, for the game of gomoku
            """
        return self.board[point] == EMPTY
    
    def play_move_gomoku(self, point, color):
        """
            Play a move of color on point, for the game of gomoku
            Returns boolean: whether move was legal
            """
        assert is_black_white(color)
        assert point != PASS
        if self.board[point] != EMPTY:
            return False
        self.board[point] = color
        self.current_player = GoBoardUtil.opponent(color)
        return True
        
    def _point_direction_check_connect_gomoko(self, point, shift):
        """
        Check if the point has connect5 condition in a direction
        for the game of Gomoko.
        """
        color = self.board[point]
        count = 1
        d = shift
        p = point
        while True:
            p = p + d
            if self.board[p] == color:
                count = count + 1
                if count == 5:
                    break
            else:
                break
        d = -d
        p = point
        while True:
            p = p + d
            if self.board[p] == color:
                count = count + 1
                if count == 5:
                    break
            else:
                break
        assert count <= 5
        return count == 5
    
    def point_check_game_end_gomoku(self, point):
        """
            Check if the point causes the game end for the game of Gomoko.
            """
        # check horizontal
        if self._point_direction_check_connect_gomoko(point, 1):
            return True
        
        # check vertical
        if self._point_direction_check_connect_gomoko(point, self.NS):
            return True
        
        # check y=x
        if self._point_direction_check_connect_gomoko(point, self.NS + 1):
            return True
        
        # check y=-x
        if self._point_direction_check_connect_gomoko(point, self.NS - 1):
            return True
        
        return False
    
    def check_game_end_gomoku(self):
        """
            Check if the game ends for the game of Gomoku.
            """
        white_points = where1d(self.board == WHITE)
        black_points = where1d(self.board == BLACK)
        
        for point in white_points:
            if self.point_check_game_end_gomoku(point):
                return True, WHITE
    
        for point in black_points:
            if self.point_check_game_end_gomoku(point):
                return True, BLACK

        return False, None

    def solve(self):
        result, move, drawMove = alphabeta.solve(self)
        if move=="First":
            if result==0:
                return 'draw',drawMove
            else:
                winner='w' if self.current_player!=WHITE else 'b'
                return winner,'NoMove'
        elif move=="NoMove":
            if result:
                return 'draw', drawMove
            else:
                winner='w' if self.current_player!=WHITE else 'b'
                return winner, move
        else:
            winner='w' if self.current_player==WHITE else 'b'
            return winner, move

    def check_pattern(self,point,have,direction_x,direction_y,moveSet,patternList,color,flag):
        for i in range(0,4):
            if have in patternList[i]:
                for dis in patternList[i][have]:
                    moveSet[i].add(point-direction_x*(dis+1)-direction_y*self.NS*(dis+1))
                #flag[0]=True
                break
        if (not (0<= point<len(self.board))) or len(have)==9:
            return
#if self.get_color(point)==BORDER or len(have)==7:
#            return
        piece=self.get_color(point)
        if piece==EMPTY:
            piece='.'
        elif piece==color:
            piece='x'
        elif piece == BORDER:
            piece='B'
        else:
            piece='o'
        have+=piece
        #print(GoBoardUtil.format_point(self._point_to_coord(point)),have,self.board[point])
        self.check_pattern(point+direction_x+direction_y*self.NS,have,direction_x,direction_y,moveSet,patternList,color,flag)

    def get_pattern_moves(self):
        """
        1. direct winning point xxxx. x.xxx xx.xx
        2. urgent blocking point xoooo.
        3. wining in 2 step point
        """
        moveSet=[set(),set(),set(),set()]
        color=self.current_player

        patternList=[{'xxxx.':{0},'xxx.x':{1},'xx.xx':{2},'x.xxx':{3},'.xxxx':{4}}, #win
                     {'oooo.':{0},'ooo.o':{1},'oo.oo':{2},'o.ooo':{3},'.oooo':{4}}, #block win
                     {'.xxx..':{1},'..xxx.':{4},'.xx.x.':{2},'.x.xx.':{3}}, #make-four
                     {'.ooo..':{1,5},'..ooo.':{0,4},'.oo.o.':{0,2,5},'.o.oo.':{0,3,5}, 'B.ooo..':{0}, '..ooo.B':{6},
                     'x.ooo..':{0}, '..ooo.x':{6} #block-open-four
                     }]

        direction_x=[1,0,1,-1]
        direction_y=[0,1,1,1]
        flag=[False]

        for point in range(0, len(self.board)):
            if flag[0]:
                break
            for direction in range(0,4):
                    self.check_pattern(point,'',direction_x[direction],direction_y[direction],moveSet,patternList,color,flag)
        
        i=0
        while i<4 and not bool(moveSet[i]): i+=1
        if i==4:
            return None
        else:
            return i, list(moveSet[i])
            
    def list_solve_point(self):
        """
        1. direct winning point xxxx. x.xxx xx.xx
        2. urgent blocking point xoooo.
        3. wining in 2 step point
        """
        moveSet=[set(),set(),set(),set()]
        color=self.current_player

        patternList=[{'xxxx.':{0},'xxx.x':{1},'xx.xx':{2},'x.xxx':{3},'.xxxx':{4}},{'oooo.':{0},'ooo.o':{1},'oo.oo':{2},'o.ooo':{3},'.oooo':{4}},{'.xxx..':{1},'..xxx.':{4},'.xx.x.':{2},'.x.xx.':{3}},{'.ooo..':{1,5},'..ooo.':{0,4},'.oo.o.':{2},'.o.oo.':{3}}]

        direction_x=[1,0,1,-1]
        direction_y=[0,1,1,1]
        flag=[False]

        for point in where1d(self.board!=BORDER):
            if flag[0]:
                break
            for direction in range(0,4):
                    self.check_pattern(point,'',direction_x[direction],direction_y[direction],moveSet,patternList,color,flag)
        
        i=0
        while i<4 and not bool(moveSet[i]):
            i+=1
        if i==4:
            return None
        else:
            return list(moveSet[i])

    def getPointRep(self, cp, point):
        value = self.board[point]
        if (value == cp):
            return "x"
        elif (value == EMPTY):
            return "."
        elif (value == BORDER):
            return "#"
        return "o"

    # dict to look up, winStr, player's list, opponent's list, point to add
    def checkThreat(self, d, s, cpList, opList, p, step):
        if s in d:
            #print("found threat", s)
            threat = d[s]
            if threat[0]:
                cpList.append(p - (threat[1] * step))
            else:
                opList.append(p - (threat[1] * step))

    # dict to look up, winStr, player's list, opponent's list, point to add
    def checkWin(self, d, s, cpList, opList, p, step):
        if s in d:
            #print("found win", s)
            p = p + (s.index(".")-4)*step
            if d[s]:
                cpList.append(p)
                return True
            else:
                opList.append(p)

    # threat = opponent's win
    # returns ([wins], [win threat], [2m wins], [2m win threats])
    def winDetection(self):
        myWins = []
        theirWins = []
        my2mWins = []
        their2mWins = []

        size = self.size
        startPoint = size + 2

        points = where1d(self.board == self.current_player)

        #print("Horizontal")
        # horizontal checks
        for rowStart in range(startPoint, startPoint + size*size + 1, size+1):
            winStr = ""
            for point in range(rowStart, rowStart + size):
                winStr += self.getPointRep(self.current_player, point)
                # check 2-move wins
                if len(winStr) == 6:
                    self.checkThreat(threatDict, winStr, my2mWins, their2mWins, point, 1)
                    # reduce the string to a 5-long string
                    winStr = winStr[1:]

                # check for 1-move wins
                if len(winStr) == 5:
                    if self.checkWin(winDict, winStr, myWins, theirWins, point, 1):
                        # return early if we found a win, because we can just play that
                        return myWins, [], [], []

        #print("Vertical")
        # vertical checks
        for colStart in range(startPoint, startPoint + size):
            winStr = ""
            for point in range(colStart, colStart + (size+1)*(size-1) + 1, size+1):
                winStr += self.getPointRep(self.current_player, point)
                if len(winStr) == 6:
                    self.checkThreat(threatDict, winStr, my2mWins, their2mWins, point, size+1)
                    winStr = winStr[1:]
                if len(winStr) == 5:
                    if self.checkWin(winDict, winStr, myWins, theirWins, point, size+1):
                        # return early if we found a win, because we can just play that
                        return myWins, [], [], []

        # diagonal I
        #print("Diag I")
        exists = size - 5
        checkRight = startPoint + 1
        checkDown = startPoint + size + 1
        dIStarts = [startPoint]
        for i in range(0, exists):
            dIStarts.append(checkDown)
            dIStarts.append(checkRight)
            checkRight += 1
            checkDown += size+1
        dSize = size
        reduceDSize = True
        for start in dIStarts:
            point = start
            winStr = ""
            for i in range(0, dSize):
                winStr += self.getPointRep(self.current_player, point)
                if len(winStr) == 6:
                    self.checkThreat(threatDict, winStr, my2mWins, their2mWins, point, size+2)
                    winStr = winStr[1:]
                if len(winStr) == 5:
                    #print(winStr)
                    if self.checkWin(winDict, winStr, myWins, theirWins, point, size+2):
                        # return early if we found a win, because we can just play that
                        return myWins, [], [], []

                point += size+2
            if reduceDSize:
                dSize -= 1
            reduceDSize = not reduceDSize

        # diagonal II
        #print("diag II")
        checkLeft = startPoint + (size-1) - 1
        checkDown = startPoint + (size-1) + (size+1)
        dIIStarts = [startPoint + size - 1]
        exists = size - 5
        for i in range(0, exists):
            dIIStarts.append(checkLeft)
            dIIStarts.append(checkDown)
            checkLeft -= 1
            checkDown += size+1
        dSize = size
        reduceDSize = True
        for start in dIIStarts:
            point = start
            winStr = ""
            for i in range(0, dSize):
                winStr += self.getPointRep(self.current_player, point)
                if len(winStr) == 6:
                    self.checkThreat(threatDict, winStr, my2mWins, their2mWins, point, size)
                    winStr = winStr[1:]
                if len(winStr) == 5:
                    #print(winStr)
                    if self.checkWin(winDict, winStr, myWins, theirWins, point, size):
                        # return early if we found a win, because we can just play that
                        return myWins, [], [], []

                point += size
            if reduceDSize:
                dSize -= 1
            reduceDSize = not reduceDSize

        return myWins, theirWins, my2mWins, their2mWins

    def _point_direction_check_connect_gomoko_heur(self, point, shift):
        color = self.board[point]
        d = shift
        p = point
        right_str = ""
        
        # TODO: optimize
        while True:
            p = p + d
            pt = self.board[p]
            if pt == color:
                right_str += "x"
            elif (pt == EMPTY):
                right_str += "."
            else:
                right_str += "?"
                break
        d = -d
        p = point
        left_str = ""
        while True:
            p = p + d
            pt = self.board[p]
            if pt == color:
                left_str += "x"
            elif (pt == EMPTY):
                left_str += "."
            else:
                left_str += "?"
                break
        
        string = left_str[::-1] + right_str
        
        score = 0
        for c in string:
            if (c == "x"):
                score += 1
            elif (c == "."):
                score += 0.5
            elif (c == "?"):
                score -= 1
        return score
    
    def point_check_game_end_gomoku_heur(self, point):
        return (self._point_direction_check_connect_gomoko_heur(point, 1))
            + (self._point_direction_check_connect_gomoko_heur(point, self.NS))
            + (self._point_direction_check_connect_gomoko_heur(point, self.NS + 1))
            + (self._point_direction_check_connect_gomoko_heur(point, self.NS - 1))
    
    def get_heuristic_score(self):
        score = 0
        
        # TODO: use a transposition table here
        current_points = where1d(self.board == self.current_player)
        enemy_points = where1d(self.board == GoBoardUtil.opponent(self.current_player))
        
        for point in current_points:
            score += self.point_check_game_end_gomoku_heur(point):
    
        for point in enemy_points:
            score -= self.point_check_game_end_gomoku_heur(point)
        
        return score
        
    # returns (score, moveThatCausedScore)
    def negaAB(self, alpha, beta, d, prev_move):
        empty_points = self.get_empty_points()
        #print(self.current_player, empty_points)
        if (d == 0):
            # TODO: maybe MCTS sim here?
            score = self.get_heuristic_score()
            if (score > self.best_move_score):
                self.best_move_score = score
                self.best_move = prev_move
                if (score == WINNER_SCORE):
                    return 1, prev_move
                elif (score == -WINNER_SCORE):
                    return -1, prev_move
            return 0, None
        if len(empty_points) == 0:
            return 0, None
        # TODO: sort points based on euclidian distance from prev_move
        point = empty_points[0]

        myWins, theirWins, my2mWins, their2mWins = self.winDetection()
        #print("winloseblock:", myWins, theirWins, my2mWins, their2mWins)
        if len(myWins) > 0:
            return 1, myWins[0]
        if len(theirWins) > 1:
            return -1, theirWins[0] # guaranteed loss because you can't handle more than one threat
        elif len(theirWins) == 1:
            if len(their2mWins) > 0:
                return -1, theirWins[0] # cannot block their two guaranteed win moves
            # must block this point
            point = theirWins[0]
            self.board[point] = self.current_player
            self.current_player = GoBoardUtil.opponent(self.current_player)
            result = self.negaAB(-beta, -alpha, d-1, point)
            v = -result[0]
            self.current_player = GoBoardUtil.opponent(self.current_player)
            self.board[point] = EMPTY
            return v, point
        if len(my2mWins) > 0:
            return 1, my2mWins[0]
        if len(their2mWins) > 1:
            return -1, their2mWins[0] # guaranteed loss, you can only block one
        elif len(their2mWins) == 1:
            # must block this point
            point = their2mWins[0]
            self.board[point] = self.current_player
            self.current_player = GoBoardUtil.opponent(self.current_player)
            result = self.negaAB(-beta, -alpha, d-1, point)
            v = -result[0]
            self.current_player = GoBoardUtil.opponent(self.current_player)
            self.board[point] = EMPTY
            return v, point
            
        while (len(empty_points) != 0):
            point = empty_points[-1] # O(1) operation
            empty_points = empty_points[:-1]
            self.board[point] = self.current_player
            bstr = ""
            for i in range(len(self.board)):
                if (i % (self.size+1) == 0): bstr += "\n"
                bstr += self.getPointRep(self.current_player, i)
            #print(bstr)
            
            if self.point_check_game_end_gomoku(point): # state.IsTerminal()
                #print("player", self.current_player, "won", point)
                self.board[point] = EMPTY
                return 1, point

            # switch current player
            self.current_player = GoBoardUtil.opponent(self.current_player)
            result = self.negaAB(-beta, -alpha, d-1, point)
            v = -result[0]
            if (v > alpha): alpha = v
            self.current_player = GoBoardUtil.opponent(self.current_player)

            # set the current player back and restore the empty point
            self.board[point] = EMPTY

            if (v >= beta): return beta, point
        return alpha, point

    def get_best_move(self):
        return self.best_move

    def get_best_move_score(self):
        return self.best_move_score
    
    def set_best_move(self, score, move):
        self.best_move_score = score
        self.best_move = move
