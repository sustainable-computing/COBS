import pdb

from diff_mpc import mpc
from diff_mpc.mpc import QuadCost, LinDx

import numpy as np
import pandas as pd
import torch
import torch.optim as optim
from torch.distributions import MultivariateNormal, Normal


class PPOLearner:
    def __init__(self, memory, T, n_ctrl, n_state, target, disturbance, eta, u_upper, u_lower,
                 step=300*3, lr=5e-4, clip_param=0.1, F_hat=None, Bd_hat=None):
        self.memory = memory
        self.clip_param = clip_param

        self.T = T
        self.step = step
        self.lr = lr
        self.n_ctrl = n_ctrl
        self.n_state = n_state
        self.eta = eta

        self.target = target
        self.dist = disturbance
        self.n_dist = self.dist.shape[1]

        if F_hat is not None:  # Load pre-trained F if provided
            print("Load pretrained F")
            self.F_hat = torch.tensor(F_hat).double().requires_grad_()
            print(self.F_hat)
        else:
            self.F_hat = torch.ones((self.n_state, self.n_state + self.n_ctrl))
            self.F_hat = self.F_hat.double().requires_grad_()

        if Bd_hat is not None:  # Load pre-trained Bd if provided
            print("Load pretrained Bd")
            self.Bd_hat = Bd_hat
        else:
            self.Bd_hat = 0.1 * np.random.rand(self.n_state, self.n_dist)
        self.Bd_hat = torch.tensor(self.Bd_hat).requires_grad_()
        print(self.Bd_hat)

        self.Bd_hat_old = self.Bd_hat.detach().clone()
        self.F_hat_old = self.F_hat.detach().clone()

        self.optimizer = optim.RMSprop([self.F_hat, self.Bd_hat], lr=self.lr)

        self.u_lower = u_lower * torch.ones(n_ctrl).double()
        self.u_upper = u_upper * torch.ones(n_ctrl).double()

    # Use the "current" flag to indicate which set of parameters to use
    def forward(self, x_init, ft, C, c, current=True, n_iters=20):
        T, n_batch, n_dist = ft.shape
        if current == True:
            F_hat = self.F_hat
            Bd_hat = self.Bd_hat
        else:
            F_hat = self.F_hat_old
            Bd_hat = self.Bd_hat_old

        x_lqr, u_lqr, objs_lqr = mpc.MPC(n_state=self.n_state,
                                         n_ctrl=self.n_ctrl,
                                         T=self.T,
                                         u_lower=self.u_lower.repeat(self.T, n_batch, 1),
                                         u_upper=self.u_upper.repeat(self.T, n_batch, 1),
                                         lqr_iter=n_iters,
                                         backprop=True,
                                         verbose=0,
                                         exit_unconverged=False,
                                         )(x_init.double(), QuadCost(C.double(), c.double()),
                                           LinDx(F_hat.repeat(self.T - 1, n_batch, 1, 1), ft.double()))
        return x_lqr, u_lqr

    def select_action(self, mu, sigma):
        if self.n_ctrl > 1:
            sigma_sq = torch.ones(mu.size()).double() * sigma ** 2
            dist = MultivariateNormal(mu, torch.diag(sigma_sq.squeeze()).unsqueeze(0))
        else:
            dist = Normal(mu, torch.ones_like(mu) * sigma)
        action = dist.sample()
        log_prob = dist.log_prob(action)
        return action, log_prob

    def evaluate_action(self, mu, actions, sigma):
        n_batch = len(mu)
        if self.n_ctrl > 1:
            cov = torch.eye(self.n_ctrl).double() * sigma ** 2
            cov = cov.repeat(n_batch, 1, 1)
            dist = MultivariateNormal(mu, cov)
        else:
            dist = Normal(mu, torch.ones_like(mu) * sigma)
        log_prob = dist.log_prob(actions.double())
        entropy = dist.entropy()
        return log_prob, entropy

    def update_parameters(self, loader, sigma):
        for i in range(1):
            for states, actions, next_states, dist, advantage, old_log_probs, C, c in loader:
                n_batch = states.shape[0]
                advantage = advantage.double()
                f = self.Dist_func(dist, current=True)  # T-1 x n_batch x n_state
                opt_states, opt_actions = self.forward(states, f, C.transpose(0, 1), c.transpose(0, 1),
                                                       current=True)  # x, u: T x N x Dim.
                log_probs, entropies = self.evaluate_action(opt_actions[0], actions, sigma)

                tau = torch.cat([states, actions], 1)  # n_batch x (n_state + n_ctrl)
                nState_est = torch.bmm(self.F_hat.repeat(n_batch, 1, 1), tau.unsqueeze(-1)).squeeze(-1) + f[
                    0]  # n_batch x n_state
                mse_loss = torch.mean((nState_est - next_states) ** 2)

                ratio = torch.exp(log_probs.squeeze() - old_log_probs)
                surr1 = ratio * advantage
                surr2 = torch.clamp(ratio, 1 - self.clip_param, 1 + self.clip_param) * advantage
                loss = -torch.min(surr1, surr2).mean()
                self.optimizer.zero_grad()
                loss.backward()
                # nn.utils.clip_grad_norm_([self.F_hat, self.Bd_hat], 100)
                self.optimizer.step()

            self.F_hat_old = self.F_hat.detach().clone()
            self.Bd_hat_old = self.Bd_hat.detach().clone()
            print(self.F_hat)
            print(self.Bd_hat)

    def Dist_func(self, d, current=False):
        if current:  # d in n_batch x n_dist x T-1
            n_batch = d.shape[0]
            ft = torch.bmm(self.Bd_hat.repeat(n_batch, 1, 1), d)  # n_batch x n_state x T-1
            ft = ft.transpose(1, 2)  # n_batch x T-1 x n_state
            ft = ft.transpose(0, 1)  # T-1 x n_batch x n_state
        else:  # d in n_dist x T-1
            ft = torch.mm(self.Bd_hat_old, d).transpose(0, 1)  # T-1 x n_state
            ft = ft.unsqueeze(1)  # T-1 x 1 x n_state
        return ft

    def Cost_function(self, cur_time):
        diag = torch.zeros(self.T, self.n_state + self.n_ctrl)
        occupied = self.dist["Occupancy Flag"][cur_time: cur_time + pd.Timedelta(seconds=(self.T - 1) * self.step)]  # T
        eta_w_flag = torch.tensor([self.eta[int(flag)] for flag in occupied]).unsqueeze(1).double()  # Tx1
        diag[:, :self.n_state] = eta_w_flag
        diag[:, self.n_state:] = 1e-6

        # pdb.set_trace()
        C = []
        for i in range(self.T):
            C.append(torch.diag(diag[i]))
        C = torch.stack(C).unsqueeze(1)  # T x 1 x (m+n) x (m+n)

        x_target = self.target[cur_time: cur_time + pd.Timedelta(seconds=(self.T - 1) * self.step)]  # in pd.Series
        x_target = torch.tensor(np.array(x_target))

        c = torch.zeros(self.T, self.n_state + self.n_ctrl)  # T x (m+n)
        c[:, :self.n_state] = -eta_w_flag * x_target
        c[:, self.n_state:] = 1  # L1-norm now!

        c = c.unsqueeze(1)  # T x 1 x (m+n)
        return C, c