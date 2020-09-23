# Gnu-RL

This is the re-implementation of [Gnu-RL: A Precocial Reinforcement Learning Solution for Building HVAC Control Using a Differentiable MPC Policy](https://dl.acm.org/citation.cfm?id=3360849).

```
@inproceedings{chen2019gnu,
  title={Gnu-RL: A Precocial Reinforcement Learning Solution for Building HVAC Control Using a Differentiable MPC Policy},
  author={Chen, Bingqing and Cai, Zicheng and Berg{\'e}s, Mario},
  booktitle={Proceedings of the 6th ACM International Conference on Systems for Energy-Efficient Buildings, Cities, and Transportation},
  pages={316--325},
  year={2019},
  organization={ACM}
}
```

### Description
Gnu-RL is a novel approach that enables practical deployment of reinforcement learning (RL) for heating, ventilation, and air conditioning (HVAC) control and requires no prior information other than historical data from existing HVAC controllers. 

Prior to any interaction with the environment, a Gnu-RL agent is pre-trained on historical data using imitation learning, which enables it to match the behavior of the existing controller. Once it is put in charge of controlling the environment, the agent continues to improve its policy end-to-end, using a policy gradient algorithm.

Specifically, Gnu-RL adopts a recently-developed [Differentiable Model Predictive Control (MPC)](http://papers.nips.cc/paper/8050-differentiable-mpc-for-end-to-end-planning-and-control.pdf) policy, which encodes domain knowledge on planning and system dynamics, making it both sample-efficient and interpretable. 