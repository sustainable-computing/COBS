# COBS: COmprehensive Building Simulator (Early access v0.1)
[![contributions welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat)](#)[![License](http://img.shields.io/badge/license-MIT-green.svg?style=flat)](https://github.com/sustainable-computing/COBS/blob/master/LICENSE)

COBS is an open-source, modular co-simulation platform for developing and comparing building control algorithms. It integrates various simulators and agent models with EnergyPlus and supports fine-grained and occupant-centric control of building subsystems. COBS provides the ability to access the state after each simulation step in EnergyPlus and to use its value to determine the control action for the next time step(s). The interface is designed similar to OpenAI Gym so that the environments written for Gym can be easily used with the simulator.

COBS is licensed under [MIT](https://github.com/sustainable-computing/COBS/blob/master/LICENSE).

This platform is developed by Tianyu Zhang (tzhang6@ualberta.ca). We acknowledge the contribution of Gaby Baasch <gaby.baasch@gmail.com>, who wrote several control agents and contributed code to this platform.

## Contributing
We welcome contributions in different forms, from bug reports to pull requests. We encourage the community to use, improve, and extend COBS by adding new occupancy and building models and sharing the implementation of control algorithms. For major changes, please open an issue to discuss how you would like to change the platform.

## Documentation
Documentation is available at https://cobs-platform.github.io

## Dependencies
Visit this [page](https://cobs-platform.github.io/dependencies.html) for the full list of dependencies.

## Acknowledgement
+ Building models (`./cobs/data/buildings/*`): The Pacific Northwest National Laboratory (PNNL)
+ Weather data (`./cobs/data/weathers/*`): The Pacific Northwest National Laboratory (PNNL)

## Cite COBS
Tianyu Zhang and Omid Ardakanian. 2020. [COBS: COmprehensive Building Simulator](https://doi.org/10.1145/3408308.3431119), In _Proceedings of the 7th ACM International Conference on Systems for Energy-Efficient Buildings, Cities, and Transportation (BuildSys '20)_. ACM, 314-315.
```
@inproceedings{10.1145/3408308.3431119,
author = {Zhang, Tianyu and Ardakanian, Omid},
title = {COBS: COmprehensive Building Simulator},
year = {2020},
isbn = {9781450380614},
publisher = {Association for Computing Machinery},
address = {New York, NY, USA},
url = {https://doi.org/10.1145/3408308.3431119},
doi = {10.1145/3408308.3431119},
booktitle = {Proceedings of the 7th ACM International Conference on Systems for Energy-Efficient Buildings, Cities, and Transportation},
pages = {314--315},
location = {Virtual Event, Japan},
series = {BuildSys ’20}
}
```
