
<!-- PROJECT SHIELDS -->
<!--
*** I'm using markdown "reference style" links for readability.
*** Reference links are enclosed in brackets [ ] instead of parentheses ( ).
*** See the bottom of this document for the declaration of the reference variables
*** for contributors-url, forks-url, etc. This is an optional, concise syntax you may use.
*** https://www.markdownguide.org/basic-syntax/#reference-style-links
-->
[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]
[![LinkedIn][linkedin-shield]][linkedin-url]



<!-- PROJECT LOGO -->
<br />
<div align="center">

  <h1 align="center">Phonendo</h1>

  <p align="center">
    Phonendo is a platform consisting of several software services that manages the entire data lifecycle from wearable device data collection to publishing them on IOTA.
    <br />
    <br />
    Phonendo is published on Wireless Networks https://link.springer.com/article/10.1007/s11276-023-03458-7 and can be cited:
    
    Moya, F., Quesada, F.J., Martínez, L. et al. 
    Phonendo: a platform for publishing wearable data on distributed ledger technologies. 
    Wireless Netw (2023). 
    https://doi.org/10.1007/s11276-023-03458-7
  <br />
    <br />
    <a href="https://github.com/sinbad2-ujaen/phonendo/blob/main/demo/phonendo_demo.mp4">View Demo</a>
    ·
    <a href="https://github.com/sinbad2-ujaen/phonendo/issues">Report Bug / Request Feature</a>
  </p>
</div>



<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
  </ol>
</details>



<!-- ABOUT THE PROJECT -->
## About The Project

[![Phonendo][product-screenshot]](https://github.com/sinbad2-ujaen/phonendo)

The Phonendo architecture adopts a microservice event-driven approach, consisting of five key components: Reader, Manager, Storage, Verifier, and Publisher. The diagram below depicts the interconnectedness of these components and highlights their primary functions. This architectural design prioritizes flexibility, scalability, and adaptability across various applications.

To facilitate rapid prototyping and leverage the extensive support within the developer community, we opted for the Node.js framework and JavaScript programming language in the development of Phonendo. HTTP was chosen as the communication protocol due to its simplicity in facilitating seamless data transfer between services.

During the implementation phase, we employed the Pine Time smartwatch (available at [https://www.pine64.org/pinetime/](https://www.pine64.org/pinetime/)) as a reference device. This choice allowed us to ensure compatibility and evaluate the integration of Phonendo with a real-world wearable device. By doing so, we were able to validate the platform's functionality and its capacity to handle data from smartwatches, which are commonly used in healthcare and fitness applications.

It is essential to acknowledge that the current implementation of Phonendo serves as a foundation for further research and development. As we continue refining the platform and exploring additional use cases, we anticipate introducing enhancements and optimizations based on empirical experimentation and user feedback.

<!-- GETTING STARTED -->
## Getting Started

### Prerequisites

This is an example of how to list things you need to use the software and how to install them.
* npm
  ```sh
  npm install npm@latest -g
  ```

* pm2
  ```sh
  npm install -g pm2
  ```

### Installation

1. Clone the repo
   ```sh
   git clone https://github.com/sinbad2-ujaen/phonendo.git
   ```
2. Install NPM packages
   ```sh
   npm install
   ```
3. Start project
   ```sh
   npm run infra:up
   ```



<!-- USAGE EXAMPLES -->
## Usage

- To start the project
   ```sh
   npm run infra:up
   ```
- To stop the project
   ```sh
   npm run infra:down
   ```
- To clean all resources
   ```sh
   npm run infra:clean
   ```
- To restart all services
   ```sh
   npm run infra:restart
   ```

Once all services are up, next step is to register a device using the Reader endpoint
``` 
curl --location 'http://127.0.0.1:3003/register' \ --header 'Content-Type: application/x-www-form-urlencoded' \ --data-urlencode 'device=XXXXXXXXXX' \ --data-urlencode 'serialNumber=XXX' \ --data-urlencode 'deviceType=SMARTWATCH'
```

Once the device is registered, Phonendo will automatically detect, connect and start listening events. In particular, it captures heartbeat events.

<!-- CONTRIBUTING -->
## Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".
Don't forget to give the project a star! Thanks again!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request



<!-- LICENSE -->
## License

Distributed under the MIT License. See `LICENSE.txt` for more information.



<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/sinbad2-ujaen/phonendo.svg?style=for-the-badge
[contributors-url]: https://github.com/sinbad2-ujaen/phonendo/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/sinbad2-ujaen/phonendo.svg?style=for-the-badge
[forks-url]: https://github.com/sinbad2-ujaen/phonendo/network/members
[stars-shield]: https://img.shields.io/github/stars/sinbad2-ujaen/phonendo.svg?style=for-the-badge
[stars-url]: https://github.com/sinbad2-ujaen/phonendo/stargazers
[issues-shield]: https://img.shields.io/github/issues/sinbad2-ujaen/phonendo.svg?style=for-the-badge
[issues-url]: https://github.com/sinbad2-ujaen/phonendo/issues
[license-shield]: https://img.shields.io/github/license/sinbad2-ujaen/phonendo.svg?style=for-the-badge
[license-url]: https://github.com/sinbad2-ujaen/phonendo/LICENSE.txt
[linkedin-shield]: https://img.shields.io/badge/-LinkedIn-black.svg?style=for-the-badge&logo=linkedin&colorB=555
[linkedin-url]: https://www.linkedin.com/in/francisco-moya/
[product-screenshot]: images/system.jpg
