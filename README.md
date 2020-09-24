# COBS: COmprehensive Building Simulator (Early access v0.1)
[![contributions welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat)](#)[![License](http://img.shields.io/badge/license-MIT-green.svg?style=flat)](https://github.com/sustainable-computing/COBS/blob/master/LICENSE)

COBS is an open-source, modular co-simulation platform for ideveloping and comparing building control algorithms. It integrates various simulators and agent models with EnergyPlus, and supports fine-grained and occupant-centric control of building subsystems. COBS provides the ability to access the state after each simulation step in EnergyPlus and to use its value to determine the control action for the next time step(s). The interface is designed similar to OpenAI Gym so that the environments written for Gym can be easily used with the simulator.

COBS is licensed under [MIT](https://github.com/sustainable-computing/COBS/blob/master/LICENSE).

## Contributing
We welcome contributions in many forms, such as bug reports, pull requests, etc., and encourage the community to use, improve and extend this platform by adding their HVAC control algorithms and/or building models. For major changes, open an issue first to discuss what you would like to do.

Thanks to Gaby Baasch <gaby.baasch@gmail.com> for implementing several control agents and contributing code to this simulator.

## Documentation
Documentation is available at https://cobs-platform.github.io

## Dependencies
Visit this [page](https://cobs-platform.github.io/dependencies.html) for the full list of dependecies.
