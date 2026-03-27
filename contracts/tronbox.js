module.exports = {
  networks: {
    nile: {
      privateKey: process.env.PRIVATE_KEY_NILE,
      userFeePercentage: 100,
      feeLimit: 1e9,
      fullHost: "https://api.nileex.io",
      network_id: "3",
    },
    mainnet: {
      privateKey: process.env.PRIVATE_KEY_MAINNET,
      userFeePercentage: 100,
      feeLimit: 1e9,
      fullHost: "https://api.trongrid.io",
      network_id: "1",
    },
    development: {
      privateKey: process.env.PRIVATE_KEY_NILE,
      userFeePercentage: 0,
      feeLimit: 1e9,
      fullHost: "http://127.0.0.1:9090",
      network_id: "9",
    },
  },
  compilers: {
    solc: {
      version: "0.8.20",
      settings: {
        optimizer: {
          enabled: true,
          runs: 200,
        },
        evmVersion: "istanbul",
      },
    },
  },
};
