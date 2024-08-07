# Copyright 2019 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""GFootball Environment."""


import types

import gymnasium as gym
import numpy as np

from gfootball.env import config, football_env, observation_preprocessing, wrappers


def _process_reward_wrappers(env, rewards):
    assert "scoring" in rewards.split(",")
    if "checkpoints" in rewards.split(","):
        env = wrappers.CheckpointRewardWrapper(env)
    return env


def _process_representation_wrappers(env, representation, channel_dimensions):
    """Wraps with necessary representation wrappers.

    Args:
      env: A GFootball gym environment.
      representation: See create_environment.representation comment.
      channel_dimensions: (width, height) tuple that represents the dimensions of
         SMM or pixels representation.
    Returns:
      Google Research Football environment.
    """
    if representation.startswith("pixels"):
        env = wrappers.PixelsStateWrapper(env, "gray" in representation, channel_dimensions)
    elif representation == "simple115":
        env = wrappers.Simple115StateWrapper(env)
    elif representation == "simple115v2":
        env = wrappers.Simple115StateWrapper(env, True)
    elif representation == "simplev1":
        env = wrappers.SimpleStateWrapper(env)
    elif representation == "extracted":
        env = wrappers.SMMWrapper(env, channel_dimensions)
    elif representation == "raw":
        pass
    else:
        raise ValueError(f"Unsupported representation: {representation}")
    return env


def _apply_output_wrappers(
    env, rewards, representation, channel_dimensions, apply_single_agent_wrappers, stacked, action_mask: bool = True
):
    """Wraps with necessary wrappers modifying the output of the environment.

    Args:
      env: A GFootball gym environment.
      rewards: What rewards to apply.
      representation: See create_environment.representation comment.
      channel_dimensions: (width, height) tuple that represents the dimensions of
         SMM or pixels representation.
      apply_single_agent_wrappers: Whether to reduce output to single agent case.
      stacked: Should observations be stacked.
    Returns:
      Google Research Football environment.
    """
    env = _process_reward_wrappers(env, rewards)
    env = _process_representation_wrappers(env, representation, channel_dimensions)
    if action_mask:
        env = wrappers.ActionMaskWrapper(env)
    if apply_single_agent_wrappers:
        if representation != "raw":
            env = wrappers.SingleAgentObservationWrapper(env)
        env = wrappers.SingleAgentRewardWrapper(env)
    if stacked:
        env = wrappers.FrameStack(env, 4)
    env = wrappers.GetStateWrapper(env)
    return env


def _apply_state_wrappers(env, representation) -> gym.Wrapper | gym.Env:
    def state_space(self):
        num_left_agents = self.engine_config.controllable_left_players
        num_right_agents = self.engine_config.controllable_right_players
        shape = (
            4 * (num_left_agents + num_right_agents)
            + self.control_config.number_of_players_agent_controls() * num_left_agents
            + 16,
        )
        state_space = gym.spaces.Box(low=-np.inf, high=np.inf, shape=shape, dtype=np.float32)
        return state_space

    def state(self) -> np.ndarray:
        def do_flatten(obj):
            """Run flatten on either python list or numpy array."""
            if type(obj) == list:
                return np.array(obj).flatten()
            return obj.flatten()

        observation_dicts = self.observation()
        first_obs_dict = observation_dicts[0]
        player_ids_agent_controls = np.array([obs_dict["active"] for obs_dict in observation_dicts])
        state = []
        # n1 * 2 - (x,y) coordinates of left team players
        # n1 * 2 - (x,y) direction of left team players
        # n2 * 2 - (x,y) coordinates of right team players
        # n2 * 2 - (x,y) direction of right team players

        # 3 - (x,y,z) - ball position
        # 3 - ball direction
        # 3 - one hot encoding of ball ownership (noone, left, right)

        # 7 - one hot encoding of `game_mode`
        # n0 * n1 - one hot encoding of which player is active  (controlled agent ids)
        # dim: 4*(n1+n2) + n0*n1 + 16
        state.extend(do_flatten(first_obs_dict["left_team"]))
        state.extend(do_flatten(first_obs_dict["left_team_direction"]))
        state.extend(do_flatten(first_obs_dict["right_team"]))
        state.extend(do_flatten(first_obs_dict["right_team_direction"]))

        state.extend(do_flatten(first_obs_dict["ball"]))
        state.extend(do_flatten(first_obs_dict["ball_direction"]))
        if first_obs_dict["ball_owned_team"] == -1:
            state.extend([1, 0, 0])
        if first_obs_dict["ball_owned_team"] == 0:
            state.extend([0, 1, 0])
        if first_obs_dict["ball_owned_team"] == 1:
            state.extend([0, 0, 1])

        state.extend(do_flatten(np.eye(7)[first_obs_dict["game_mode"]]))

        for p_i in player_ids_agent_controls:
            state.extend(do_flatten(np.eye(len(first_obs_dict["left_team"]))[p_i]))

        return np.array(state, dtype=np.float32)

    if representation in ["simplev1"]:
        env.__class__.state_space = property(state_space)
        env.state = types.MethodType(state, env)

    return env


def create_environment(
    env_name="",
    stacked=False,
    representation="extracted",
    rewards="scoring",
    write_goal_dumps=False,
    write_full_episode_dumps=False,
    render=False,
    write_video=False,
    dump_frequency=1,
    logdir="",
    extra_players=None,
    number_of_left_players_agent_controls=1,
    number_of_right_players_agent_controls=0,
    channel_dimensions=(observation_preprocessing.SMM_WIDTH, observation_preprocessing.SMM_HEIGHT),
    other_config_options={},
) -> gym.Env | gym.Wrapper:
    """Creates a Google Research Football environment.

    Args:
      env_name: a name of a scenario to run, e.g. "11_vs_11_stochastic".
        The list of scenarios can be found in directory "scenarios".
      stacked: If True, stack 4 observations, otherwise, only the last
        observation is returned by the environment.
        Stacking is only possible when representation is one of the following:
        "pixels", "pixels_gray" or "extracted".
        In that case, the stacking is done along the last (i.e. channel)
        dimension.
      representation: String to define the representation used to build
        the observation. It can be one of the following:
        'pixels': the observation is the rendered view of the football field
          downsampled to 'channel_dimensions'. The observation size is:
          'channel_dimensions'x3 (or 'channel_dimensions'x12 when "stacked" is
          True).
        'pixels_gray': the observation is the rendered view of the football field
          in gray scale and downsampled to 'channel_dimensions'. The observation
          size is 'channel_dimensions'x1 (or 'channel_dimensions'x4 when stacked
          is True).
        'extracted': also referred to as super minimap. The observation is
          composed of 4 planes of size 'channel_dimensions'.
          Its size is then 'channel_dimensions'x4 (or 'channel_dimensions'x16 when
          stacked is True).
          The first plane P holds the position of players on the left
          team, P[y,x] is 255 if there is a player at position (x,y), otherwise,
          its value is 0.
          The second plane holds in the same way the position of players
          on the right team.
          The third plane holds the position of the ball.
          The last plane holds the active player.
        'simple115'/'simple115v2': the observation is a vector of size 115.
          It holds:
           - the ball_position and the ball_direction as (x,y,z)
           - one hot encoding of who controls the ball.
             [1, 0, 0]: nobody, [0, 1, 0]: left team, [0, 0, 1]: right team.
           - one hot encoding of size 11 to indicate who is the active player
             in the left team.
           - 11 (x,y) positions for each player of the left team.
           - 11 (x,y) motion vectors for each player of the left team.
           - 11 (x,y) positions for each player of the right team.
           - 11 (x,y) motion vectors for each player of the right team.
           - one hot encoding of the game mode. Vector of size 7 with the
             following meaning:
             {NormalMode, KickOffMode, GoalKickMode, FreeKickMode,
              CornerMode, ThrowInMode, PenaltyMode}.
           Can only be used when the scenario is a flavor of normal game
           (i.e. 11 versus 11 players).
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
             - (x,y,z) - ball position
             - (Δx,Δy,Δz) ball direction
             - one hot encoding of ball ownership (noone, left, right)
             - one hot encoding of `game_mode`
             - one hot encoding of which player is active (agent id), size n1
            Total dim:
              4 * 2 + (n1-1) * 2 * 3 + n2 * 2 * 3 + 3 + 3 + 3 + n1 + 7
              = 7 * n1 + 6 * n2 + 18
      rewards: Comma separated list of rewards to be added.
         Currently supported rewards are 'scoring' and 'checkpoints'.
      write_goal_dumps: whether to dump traces up to 200 frames before goals.
      write_full_episode_dumps: whether to dump traces for every episode.
      render: whether to render game frames.
         Must be enable when rendering videos or when using pixels
         representation.
      write_video: whether to dump videos when a trace is dumped.
      dump_frequency: how often to write dumps/videos (in terms of # of episodes)
        Sub-sample the episodes for which we dump videos to save some disk space.
      logdir: directory holding the logs.
      extra_players: A list of extra players to use in the environment.
          Each player is defined by a string like:
          "$player_name:left_players=?,right_players=?,$param1=?,$param2=?...."
      number_of_left_players_agent_controls: Number of left players an agent
          controls.
      number_of_right_players_agent_controls: Number of right players an agent
          controls.
      channel_dimensions: (width, height) tuple that represents the dimensions of
         SMM or pixels representation.
      other_config_options: dict that allows directly setting other options in
         the Config
    Returns:
      Google Research Football environment.
    """
    assert env_name

    scenario_config = config.Config({"level": env_name}).ScenarioConfig()
    players = [
        (
            "agent:left_players=%d,right_players=%d"
            % (number_of_left_players_agent_controls, number_of_right_players_agent_controls)
        )
    ]

    # Enable MultiAgentToSingleAgent wrapper?
    multiagent_to_singleagent = False
    if scenario_config.control_all_players:
        if number_of_left_players_agent_controls in [0, 1] and number_of_right_players_agent_controls in [0, 1]:
            multiagent_to_singleagent = True
            players = [
                (
                    "agent:left_players=%d,right_players=%d"
                    % (
                        scenario_config.controllable_left_players if number_of_left_players_agent_controls else 0,
                        scenario_config.controllable_right_players if number_of_right_players_agent_controls else 0,
                    )
                )
            ]

    if extra_players is not None:
        players.extend(extra_players)
    config_values = {
        "dump_full_episodes": write_full_episode_dumps,
        "dump_scores": write_goal_dumps,
        "players": players,
        "level": env_name,
        "tracesdir": logdir,
        "write_video": write_video,
    }
    config_values.update(other_config_options)
    c = config.Config(config_values)

    env = football_env.FootballEnv(c)
    env = _apply_state_wrappers(env, representation)
    if multiagent_to_singleagent:
        env = wrappers.MultiAgentToSingleAgent(
            env, number_of_left_players_agent_controls, number_of_right_players_agent_controls
        )
    if dump_frequency > 1:
        env = wrappers.PeriodicDumpWriter(env, dump_frequency, render)
    elif render:
        env.render()
    env = _apply_output_wrappers(
        env,
        rewards,
        representation,
        channel_dimensions,
        (number_of_left_players_agent_controls + number_of_right_players_agent_controls == 1),
        stacked,
        action_mask=c._values.get("action_mask", True),
    )

    return env


def create_remote_environment(
    username,
    token,
    model_name="",
    track="",
    stacked=False,
    representation="raw",
    rewards="scoring",
    channel_dimensions=(observation_preprocessing.SMM_WIDTH, observation_preprocessing.SMM_HEIGHT),
    include_rendering=False,
):
    """Creates a remote Google Research Football environment.

    Args:
      username: User name.
      token: User token.
      model_name: A model identifier to be displayed on the leaderboard.
      track: which competition track to connect to.
      stacked: If True, stack 4 observations, otherwise, only the last
        observation is returned by the environment.
        Stacking is only possible when representation is one of the following:
        "pixels", "pixels_gray" or "extracted".
        In that case, the stacking is done along the last (i.e. channel)
        dimension.
      representation: See create_environment.representation comment.
      rewards: Comma separated list of rewards to be added.
         Currently supported rewards are 'scoring' and 'checkpoints'.
      channel_dimensions: (width, height) tuple that represents the dimensions of
         SMM or pixels representation.
      include_rendering: Whether to return frame as part of the output.
    Returns:
      Google Research Football environment.
    """
    from gfootball.env import remote_football_env

    env = remote_football_env.RemoteFootballEnv(
        username, token, model_name=model_name, track=track, include_rendering=include_rendering
    )
    env = _apply_output_wrappers(
        env, rewards, representation, channel_dimensions, env._config.number_of_players_agent_controls() == 1, stacked
    )
    return env
