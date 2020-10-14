import pickle, pdb, os
import numpy as np
import pandas as pd
import torch
import torch.utils.data as data


class Dataset(data.Dataset):
    def __init__(self, states, actions, next_states, disturbance, rewards, old_logprobs, CC, cc):
        self.states = states
        self.actions = actions
        self.next_states = next_states
        self.disturbance = disturbance
        self.rewards = rewards
        self.old_logprobs = old_logprobs
        self.CC = CC
        self.cc = cc

    def __len__(self):
        return len(self.states)

    def __getitem__(self, index):
        return self.states[index], self.actions[index], self.next_states[index], self.disturbance[index], self.rewards[index], self.old_logprobs[index], self.CC[index], self.cc[index]


class PPOAgent:
    def __init__(self, tol_eps, learner, multiplier, gamma, update_episode, obs_name, save_path):
        self.tol_eps = tol_eps
        self.learner = learner
        self.multiplier = multiplier
        self.gamma = gamma
        self.update_episode = update_episode
        self.obs_name = obs_name
        # globals vars
        self.timeStamp = []
        self.observations = []
        self.actions_taken = []
        self.perf = []
        # episode vars
        self.log_probs = []
        self.rewards = []
        self.real_rewards = []
        self.old_log_probs = []
        self.states = []
        self.disturbance = []
        self.actions = []  # Save for Parameter Updates
        self.CC = []
        self.cc = []
        self.sigma = 1
        self.save_path = save_path

    def agent_start(self, obvs, i_episode):
        (last_state, obs_dict, obs, cur_time) = obvs
        self.log_probs = []
        self.rewards = []
        self.real_rewards = []
        self.old_log_probs = []
        self.states = []
        self.disturbance = []
        self.actions = []  # Save for Parameter Updates
        self.CC = []
        self.cc = []
        self.sigma = 1 - 0.9 * i_episode / self.tol_eps

        td = pd.Timedelta(seconds=(self.learner.T - 2) * self.learner.step)
        dt = np.array(self.learner.dist[cur_time: cur_time + td])  # T-1 x n_dist
        dt = torch.tensor(dt).transpose(0, 1)  # n_dist x T-1
        ft = self.learner.Dist_func(dt)  # T-1 x 1 x n_state
        C, c = self.learner.Cost_function(cur_time)
        opt_states, opt_actions = self.learner.forward(last_state, ft, C, c, current=False)  # x, u: T x 1 x Dim.
        action, old_log_prob = self.learner.select_action(opt_actions[0], self.sigma)
        if action.item() < 0:
            action = torch.zeros_like(action)
        SAT_stpt = obs_dict["MA Temp."] + max(0, action.item())
        # If the room gets too warm during occupied period, uses outdoor air for free cooling.
        if (obs_dict["Indoor Temp."] > obs_dict["Indoor Temp. Setpoint"]) & (obs_dict["Occupancy Flag"] == 1):
            SAT_stpt = obs_dict["Outdoor Temp."]

        self.old_log_probs.append(old_log_prob)
        self.CC.append(C)
        self.cc.append(c)
        # vv state vars
        self.disturbance.append(dt)
        self.states.append(last_state)
        if len(self.observations) == 0: self.observations.append(obs)
        # vv action vars
        self.actions.append(action)
        self.actions_taken.append([action.item(), SAT_stpt])
        if len(self.timeStamp) == 0: self.timeStamp.append(cur_time)

        return action, SAT_stpt

    def agent_step(self, reward, obvs):
        (last_state, obs_dict, obs, cur_time) = obvs
        self.real_rewards.append(reward)
        self.rewards.append(reward.double() / self.multiplier)

        dt = np.array(self.learner.dist[cur_time: cur_time + pd.Timedelta(
            seconds=(self.learner.T - 2) * self.learner.step)])  # T-1 x n_dist
        dt = torch.tensor(dt).transpose(0, 1)  # n_dist x T-1
        ft = self.learner.Dist_func(dt)  # T-1 x 1 x n_state
        C, c = self.learner.Cost_function(cur_time)
        opt_states, opt_actions = self.learner.forward(last_state, ft, C, c, current=False)  # x, u: T x 1 x Dim.
        action, old_log_prob = self.learner.select_action(opt_actions[0], self.sigma)
        if action.item() < 0:
            action = torch.zeros_like(action)
        SAT_stpt = obs_dict["MA Temp."] + max(0, action.item())
        # If the room gets too warm during occupied period, uses outdoor air for free cooling.
        if (obs_dict["Indoor Temp."] > obs_dict["Indoor Temp. Setpoint"]) & (obs_dict["Occupancy Flag"] == 1):
            SAT_stpt = obs_dict["Outdoor Temp."]

        self.old_log_probs.append(old_log_prob)
        self.CC.append(C)
        self.cc.append(c)
        # vv state vars
        self.disturbance.append(dt)
        self.states.append(last_state)
        self.observations.append(obs)
        self.timeStamp.append(cur_time)
        # vv action vars
        self.actions.append(action)
        self.actions_taken.append([action.item(), SAT_stpt])

        return action, SAT_stpt

    def agent_end(self, reward, obvs, i_episode):
        (last_state, obs_dict, obs, cur_time) = obvs
        dt = np.array(self.learner.dist[cur_time: cur_time + pd.Timedelta(
            seconds=(self.learner.T - 2) * self.learner.step)])
        dt = torch.tensor(dt).transpose(0, 1)
        (last_state, obs_dict, obs, _) = obvs
        self.real_rewards.append(reward)
        self.rewards.append(reward.double() / self.multiplier)
        # vv state vars
        self.disturbance.append(dt)
        self.states.append(last_state)
        self.observations.append(obs)
        self.timeStamp.append(cur_time)

        self.store_memory()
        self.end_episode(cur_time, i_episode)

    def end_episode(self, cur_time, i_episode):
        # if -1, do not update parameters
        # print('lengths', len(self.observations), len(self.timeStamp), len(self.actions_taken))

        if self.update_episode == -1:
            pass
        elif (self.learner.memory.len >= self.update_episode) & (i_episode % self.update_episode == 0):
            batch_states, batch_actions, b_next_states, batch_dist, batch_rewards, \
            batch_old_logprobs, batch_CC, batch_cc = self.learner.memory.sample_batch(self.update_episode)
            batch_set = Dataset(batch_states, batch_actions, b_next_states, batch_dist, batch_rewards,
                                batch_old_logprobs, batch_CC, batch_cc)
            # pdb.set_trace()
            batch_loader = data.DataLoader(batch_set, batch_size=48, shuffle=True, num_workers=2)
            self.learner.update_parameters(batch_loader, self.sigma)

        self.perf.append([np.mean(self.real_rewards), np.std(self.real_rewards)])
        print("{}, reward: {}".format(cur_time, np.mean(self.real_rewards)))

    def store_memory(self):
        def advantage_func(rewards, gamma):
            r = torch.zeros(1, 1).double()
            t = len(rewards)
            advantage = torch.zeros((t, 1)).double()

            for i in reversed(range(len(rewards))):
                r = gamma * r + rewards[i]
                advantage[i] = r
            return advantage

        advantages = advantage_func(self.rewards, self.gamma)
        old_log_probs = torch.stack(self.old_log_probs).squeeze().detach().clone()
        next_states = torch.stack(self.states[1:]).squeeze(1)
        states = torch.stack(self.states[:-1]).squeeze(1)
        actions = torch.stack(self.actions).squeeze(1).detach().clone()
        CC = torch.stack(self.CC).squeeze()  # n_batch x T x (m+n) x (m+n)
        cc = torch.stack(self.cc).squeeze()  # n_batch x T x (m+n)
        disturbance = torch.stack(self.disturbance)  # n_batch x T x n_dist
        self.learner.memory.append(states, actions, next_states, advantages, old_log_probs, disturbance, CC, cc)
