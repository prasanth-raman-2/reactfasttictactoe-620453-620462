from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Literal, Any
from uuid import uuid4

# OpenAPI tags for documentation
openapi_tags = [
    {"name": "Game", "description": "Game session management: creation, retrieval, moves, and status."}
]

app = FastAPI(
    title="Tic Tac Toe Backend",
    description="RESTful backend for a web-based Tic Tac Toe game. Provides APIs for new game creation, move submission, and state retrieval.",
    version="1.0.0",
    openapi_tags=openapi_tags,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for game states
games: Dict[str, Dict[str, Any]] = {}

# --- Models ---
class NewGameRequest(BaseModel):
    """Request model to start a new game."""
    starting_player: Literal["X", "O"] = Field("X", description="Player to make the first move ('X' or 'O')")

class GameState(BaseModel):
    """Represents the state of a game."""
    game_id: str = Field(..., description="Unique identifier for the game")
    board: List[List[Optional[Literal["X", "O"]]]] = Field(..., description="3x3 board of the Tic Tac Toe game")
    current_player: Literal["X", "O"] = Field(..., description="Player whose turn is next")
    status: Literal["IN_PROGRESS", "X_WON", "O_WON", "DRAW"] = Field(..., description="Current status of the game")
    winner: Optional[Literal["X", "O"]] = Field(None, description="Winner of the game, if any")

class MoveRequest(BaseModel):
    """Request model for submitting a move."""
    row: int = Field(..., ge=0, le=2, description="Row index (0-2)")
    col: int = Field(..., ge=0, le=2, description="Column index (0-2)")
    player: Literal["X", "O"] = Field(..., description="Player making the move ('X' or 'O')")

class MoveResponse(BaseModel):
    """Response model after submitting a move."""
    board: List[List[Optional[Literal["X", "O"]]]] = Field(..., description="Board after the move")
    status: Literal["IN_PROGRESS", "X_WON", "O_WON", "DRAW"] = Field(..., description="Game status after the move")
    winner: Optional[Literal["X", "O"]] = Field(None, description="Winner, if determined")


# Utility Functions
def check_winner(board: List[List[Optional[str]]]) -> Optional[str]:
    for symbol in ["X", "O"]:
        for i in range(3):
            if all(cell == symbol for cell in board[i]):  # rows
                return symbol
            if all(row[i] == symbol for row in board):    # columns
                return symbol
        # Diagonals
        if all(board[d][d] == symbol for d in range(3)) or all(board[d][2 - d] == symbol for d in range(3)):
            return symbol
    return None

def is_draw(board: List[List[Optional[str]]]) -> bool:
    return all(cell in ("X", "O") for row in board for cell in row)

def get_game_status(board: List[List[Optional[str]]]) -> (str, Optional[str]):
    winner = check_winner(board)
    if winner == "X":
        return "X_WON", winner
    if winner == "O":
        return "O_WON", winner
    if is_draw(board):
        return "DRAW", None
    return "IN_PROGRESS", None

# --- API Endpoints ---

@app.get("/", tags=["Game"])
def health_check():
    """
    Health check endpoint for backend.
    """
    return {"message": "Healthy"}

# PUBLIC_INTERFACE
@app.post("/game", response_model=GameState, tags=["Game"], summary="Start a new game", description="Creates a new Tic Tac Toe game and returns its state.")
def start_new_game(req: NewGameRequest):
    """
    Starts a new Tic Tac Toe game.
    - **starting_player**: which player goes first, "X" or "O"
    Returns: game state including ID, board, turn, and status.
    """
    game_id = str(uuid4())
    board = [[None for _ in range(3)] for _ in range(3)]
    state = {
        "game_id": game_id,
        "board": board,
        "current_player": req.starting_player,
        "status": "IN_PROGRESS",
        "winner": None
    }
    games[game_id] = state
    return GameState(**state)

# PUBLIC_INTERFACE
@app.get("/game/{game_id}", response_model=GameState, tags=["Game"], summary="Get game state", description="Retrieve the current state of a Tic Tac Toe game by its ID.")
def get_game_state(game_id: str):
    """
    Retrieves the state of the game for a given game_id.
    Returns: game state including board, status, and whose turn.
    """
    game = games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return GameState(**game)

# PUBLIC_INTERFACE
@app.post("/game/{game_id}/move", response_model=MoveResponse, tags=["Game"], summary="Submit a move", description="Submits a move for a game and updates the state if the move is valid.")
def make_move(game_id: str, req: MoveRequest):
    """
    Submit a move for a given game:
    - **row** and **col**: Position (0-2)
    - **player**: 'X' or 'O'
    Returns the board after the move, current status, and winner if determined.
    """
    game = games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    board = game["board"]
    if game["status"] != "IN_PROGRESS":
        raise HTTPException(status_code=409, detail="Game is already over")

    # Validate it's the correct player's turn
    if req.player != game["current_player"]:
        raise HTTPException(status_code=400, detail="It's not this player's turn")

    # Validate move legality
    if not (0 <= req.row < 3 and 0 <= req.col < 3):
        raise HTTPException(status_code=400, detail="Move out of bounds")
    if board[req.row][req.col] is not None:
        raise HTTPException(status_code=400, detail="Cell already occupied")

    board[req.row][req.col] = req.player

    # Check new status
    status, winner = get_game_status(board)
    game["status"] = status
    game["winner"] = winner
    # Switch turn if game not over
    if status == "IN_PROGRESS":
        game["current_player"] = "O" if req.player == "X" else "X"

    return MoveResponse(board=board, status=status, winner=winner)
