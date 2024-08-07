# Google Research Football with Gymnasium and PettingZoo Compatibility

## Features

### Friendly Installation

Update `CMakeLists.txt` and make gfootball easier to install in virtual python environments.


### Compact Representation for Academy Scenarios
See [gfootball/env/\_\_init\_\_.py](./gfootball/__init__.py):

```md
'simplev1': a compact simple representation, adapted from https://github.com/YuriCat/TamakEriFever, which is the implementation of 5th place solution in [gfootball Kaggle Competition](https://www.kaggle.com/c/google-football/discussion/203412).
NOTE: this representation is only designed for cooperative MARL in academy scenarios.
It holds:
    - (x,y) coordinate of current player
    - (x,y) direction of current player
    - (is_sprinting, is_dribbling) agent status
    - (Δx,Δy) relative coordinates of other left team players, size (n1-1) * 2 
    - (Δx,Δy) relative coordinates of right team players, size n2 * 2
    - (Δx,Δy) relative coordinate of current player to the ball
    - (x,y) coordinates of other left team players, size (n1-1) * 2 
    - (x,y) direction of other left team players, size (n1-1) * 2
    - (x,y) coordinates of right team players, size n2 * 2
    - (x,y) direction of right team players, size n2 * 2 
    - (x,y,z) ball position
    - (Δx,Δy,Δz) ball direction
    - one hot encoding of ball ownership (none, left, right)
    - one hot encoding of `game_mode`
    - one hot encoding of which player is active (agent id), size n1
Total dim:
    4 * 2 + (n1-1) * 2 * 3 + n2 * 2 * 3 + 3 + 3 + 3 + n1 + 7
    = 7 * n1 + 6 * n2 + 18

In 'simplev1' representation, we also provide `state` function, which holds:
    - (x,y) coordinates of left team players
    - (x,y) direction of left team players
    - (x,y) coordinates of right team players
    - (x,y) direction of right team players

    - (x,y,z) - ball position
    - (x,y,z) - ball direction
    - (x,y,z) - one hot encoding of ball ownership (none, left, right)

    - one hot encoding of `game_mode`
    - one hot encoding of which player is active (controlled player ids)
Total dim: 
    4*(n1+n2) + n0*n1 + 16
```

`n0`, `n1`, `n2` represent number of players in control, number of players in the left team, and number of players in the right team.

### Action Masks

Action masks based on simple rules are returned as `info["action_mask"]` by default, you can disable by passing `other_config_options={"action_mask":False})` when initializing.


### Compatibility with Gymnasium

- Modify `step` to return `terminated` and `truncated`.
- Modify `reset` to maintain a consistent `np_random` in the environment. Refer to <https://gymnasium.farama.org/api/env/#gymnasium.Env.reset>.
- Fix the off-by-one bug: origin gfootball run 401 steps when `game_duration` is set to 400.

### Compatibility with PettingZoo

Implement pettingzoo parallel apis for gfootball, as in [gfootball/gfootball\_pettingzoo\_v1.py](gfootball/gfootball_pettingzoo_v1.py) and pass the `parallel_api_test`.

## Installation

### Dependency
```shell
# system dependence
sudo apt-get install git cmake build-essential libgl1-mesa-dev libsdl2-dev \
libsdl2-image-dev libsdl2-ttf-dev libsdl2-gfx-dev libboost-all-dev \
libdirectfb-dev libst-dev mesa-utils xvfb x11vnc
# pip dependence
pip install -U pip setuptools psutil wheel
conda install anaconda::py-boost -y
```

### Install gfootball
#### 1. PyPi from sources
```shell
pip install git+https://github.com/xihuai18/GFootball-Gymnasium-Pettingzoo.git
```
#### 2. install from GitHub sources
```shell
git clone https://github.com/xihuai18/GFootball-Gymnasium-Pettingzoo.git
cd GFootball-Gymnasium-Pettingzoo
pip install -r requirements.txt
pip install .
```

Other installation problems may be found in the original [README](https://github.com/google-research/football).

`libffi.so.7` may not be included in your environment variables, adding it before running gfootball.

```shell
export LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libffi.so.7 
```

## Test

```shell
export LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libffi.so.7 
# gymnasium apis
python -c "import gymnasium as gym; import gfootball; env = gym.make('GFootball/academy_3_vs_1_with_keeper-simplev1-v0'); print(env.reset(seed=0)); print(env.step([0]))"

# pettingzoo apis
python -c "from gfootball import gfootball_pettingzoo_v1; env = gfootball_pettingzoo_v1.parallel_env('academy_3_vs_1_with_keeper', representation='simplev1', number_of_left_players_agent_controls=2); print(env.reset(seed=0)); print(env.step({'player_0':0, 'player_1':0}))"
```