from diff_mpc import mpc
from diff_mpc.mpc import QuadCost, LinDx

import numpy as np
import pandas as pd
import torch
import torch.optim as optim


class ImitationLearner:
    def __init__(self, n_state, n_ctrl, n_dist, disturbance, target, u_upper, u_lower, step,
                 lr, planning_horizon=12, eta=5):
        self.n_state = n_state
        self.n_ctrl = n_ctrl
        self.n_dist = n_dist
        self.disturbance = disturbance
        self.target = target
        self.step = step
        self.T = planning_horizon
        self.eta_max = eta
        self.eta = [0.1, eta]
        
        # My Initial Guess
        self.F_hat = torch.ones((self.n_state, self.n_state+self.n_ctrl))
        self.F_hat[0, 0] = 0.9
        self.F_hat[0, 1] = 0.3
        self.F_hat = self.F_hat.double().requires_grad_()
        
        self.Bd_hat = np.random.rand(self.n_state, self.n_dist)
        self.Bd_hat = torch.tensor(self.Bd_hat).requires_grad_()
        
        self.optimizer = optim.Adam([self.F_hat, self.Bd_hat], lr=lr)
    
        self.u_lower = u_lower * torch.ones(self.T, 1, n_ctrl).double()
        self.u_upper = u_upper * torch.ones(self.T, 1, n_ctrl).double()
    
    def Cost_function(self, cur_time):
        diag = torch.zeros(self.T, self.n_state + self.n_ctrl)
        occupied = self.disturbance["Occupancy Flag"][cur_time:cur_time + pd.Timedelta(seconds=(self.T-1) * self.step)]
        occupied = np.array(occupied)
        if len(occupied)<self.T:
            occupied = np.pad(occupied, ((0, self.T-len(occupied)), ), 'edge')
        eta_w_flag = torch.tensor([self.eta[int(flag)] for flag in occupied]).unsqueeze(1).double()  # Tx1
        diag[:, :self.n_state] = eta_w_flag
        diag[:, self.n_state:] = 0.001
        
        C = []
        for i in range(self.T):
            C.append(torch.diag(diag[i]))
        C = torch.stack(C).unsqueeze(1)  # T x 1 x (m+n) x (m+n)
        
        x_target = self.target[cur_time : cur_time + pd.Timedelta(seconds=(self.T-1) * self.step)]  # in pd.Series
        x_target = np.array(x_target)
        if len(x_target)<self.T:
            x_target = np.pad(x_target, ((0, self.T-len(x_target)), (0, 0)), 'edge')
        x_target = torch.tensor(x_target)
        
        c = torch.zeros(self.T, self.n_state+self.n_ctrl)  # T x (m+n)
        c[:, :self.n_state] = -eta_w_flag*x_target
        c[:, self.n_state:] = 1  # L1-norm now! Check
        c = c.unsqueeze(1)  # T x 1 x (m+n)
        return C, c
    
    def forward(self, x_init, C, c, cur_time):
        dt = np.array(self.disturbance[cur_time: cur_time + pd.Timedelta(seconds=(self.T-2) * self.step)])  # T-1 x n_dist
        if len(dt)<self.T-1:
            dt = np.pad(dt, ((0, self.T-1-len(dt)), (0, 0)), 'edge')
        dt = torch.tensor(dt).transpose(0, 1)  # n_dist x T-1
        
        ft = torch.mm(self.Bd_hat, dt).transpose(0, 1)  # T-1 x n_state
        ft = ft.unsqueeze(1)  # T-1 x 1 x n_state
        
        x_pred, u_pred, _ = mpc.MPC(n_state=self.n_state,
                                    n_ctrl=self.n_ctrl,
                                    T=self.T,
                                    u_lower=self.u_lower,
                                    u_upper=self.u_upper,
                                    lqr_iter=20,
                                    verbose=0,
                                    exit_unconverged=False,
                                    )(x_init, QuadCost(C.double(), c.double()),
                                      LinDx(self.F_hat.repeat(self.T-1, 1, 1, 1),  ft))
        
        return x_pred[1, 0, :], u_pred[0, 0, :] # Dim.
    
    def predict(self, x_init, action, cur_time):
        dt = np.array(self.disturbance.loc[cur_time]) # n_dist
        dt = torch.tensor(dt).unsqueeze(1) # n_dist x 1
        ft = torch.mm(self.Bd_hat, dt) # n_state x 1
        tau = torch.stack([x_init, action]) # (n_state + n_ctrl) x 1
        next_state  = torch.mm(self.F_hat, tau) + ft # n_state x 1
        return next_state
                                    
    def update_parameters(self, x_true, u_true, x_pred, u_pred):
        # Every thing in T x Dim.
        state_loss = torch.mean((x_true.double() - x_pred)**2)
        action_loss = torch.mean((u_true.double() - u_pred)**2)
        
        # Note: args.eta balances the importance between predicting states and predicting actions
        traj_loss = self.eta_max*state_loss + action_loss
        print("From state {}, From action {}".format(state_loss, action_loss))
        self.optimizer.zero_grad()
        traj_loss.backward()
        self.optimizer.step()
#         print(self.F_hat)
#         print(self.Bd_hat)
        return state_loss.detach(), action_loss.detach()


def evaluate_performance(x_true, u_true, x_pred, u_pred):
    state_loss = torch.mean((x_true.double() - x_pred)**2)
    action_loss = torch.mean((u_true.double() - u_pred)**2)
    return state_loss, action_loss