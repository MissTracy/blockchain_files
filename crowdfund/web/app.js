import {
    createPublicClient, createWalletClient, custom, http,
    parseEther, formatEther, ContractFunctionRevertedError,
  } from './vendor/viem.js';
  
  const $ = (id) => document.getElementById(id);
  const when = (seconds) => new Date(Number(seconds) * 1000).toLocaleString();
  
  // Everything the page knows about the contract comes from deployment.json.
  let cfg, chain, publicClient;
  
  // What the page knows about the wallet.
  let walletClient;
  let wallet = null; // { name, provider }
  let account = null;
  let walletChainId = null;
  let busy = false; // true while a transaction is in progress
  
  function say(id, text, cls = '') {
    const el = $(id);
    el.textContent = text;
    el.className = cls;
  }
  
  // Turn a failure into a sentence the user can act on.
  function explain(err) {
    if (typeof err?.walk !== 'function') return err?.message ?? String(err);
    if (err.walk((e) => e?.code === 4001)) return 'You rejected the request in the wallet. Nothing was sent.';
    const revert = err.walk((e) => e instanceof ContractFunctionRevertedError);
    if (revert) {
      const name = revert.data?.errorName;
      const a = revert.data?.args ?? [];
      switch (name) {
        case 'ZeroContribution': return 'The contract rejected it: the amount must be more than zero.';
        case 'CampaignEnded': return `The contract rejected it: the campaign ended at ${when(a[0])}, so contributions are closed.`;
        case 'CampaignStillRunning': return `The contract rejected it: the campaign runs until ${when(a[0])}.`;
        case 'NotCreator': return 'The contract rejected it: only the account that created the campaign can withdraw.';
        case 'GoalNotReached': return `The contract rejected it: goal not reached (${formatEther(a[0])} of ${formatEther(a[1])} ETH raised).`;
        case 'GoalReached': return 'The contract rejected it: the goal was met, so refunds are closed.';
        case 'AlreadyWithdrawn': return 'The contract rejected it: the funds were already withdrawn.';
        case 'NothingToRefund': return 'The contract rejected it: this account has nothing to refund.';
        default: return `The contract rejected it (${name ?? 'unknown reason'}).`;
      }
    }
    return err.shortMessage ?? err.message;
  }
  
  async function loadConfig() {
    const res = await fetch('../deployment.json', { cache: 'no-store' });
    if (!res.ok) throw new Error('Could not load ../deployment.json. Copy deployment.example.json to deployment.json first.');
    const c = await res.json();
    const ok = Number.isInteger(c.chainId) && /^0x[0-9a-fA-F]{40}$/.test(c.address)
      && typeof c.rpcUrl === 'string' && Array.isArray(c.abi) && Number.isInteger(c.deployBlock);
    if (!ok) throw new Error('deployment.json needs chainId, rpcUrl, address, deployBlock and abi.');
    return c;
  }
  
  // Read the contract through the page's own RPC connection; no wallet is needed for this.
  async function refresh() {
    const read = (functionName, args) =>
      publicClient.readContract({ address: cfg.address, abi: cfg.abi, functionName, args });
    const [creator, goal, deadline, raised, withdrawn, block] = await Promise.all([
      read('creator'), read('goal'), read('deadline'), read('totalRaised'), read('withdrawn'),
      publicClient.getBlock(),
    ]);
    $('v-creator').textContent = creator;
    $('v-goal').textContent = `${formatEther(goal)} ETH`;
    $('v-raised').textContent = `${formatEther(raised)} ETH`;
    $('v-deadline').textContent = when(deadline);
    // The chain's clock is the contract's clock, so compare with the latest block, not the computer clock.
    const ended = block.timestamp >= deadline;
    const status = !ended ? 'Running'
      : withdrawn ? 'Ended, funds withdrawn'
        : raised >= goal ? 'Ended, goal met' : 'Ended, goal missed';
    $('v-status').textContent = status;
    if (account) {
      const mine = await read('contributions', [account]);
      $('w-contrib').textContent = `${formatEther(mine)} ETH`;
    } else {
      $('w-contrib').textContent = '-';
    }
  }
  
  const short = (a) => `${a.slice(0, 6)}...${a.slice(-4)}`;
  const seen = new Map(); // events already listed, keyed by block and log index
  
  function renderEvents() {
    const list = $('events');
    list.replaceChildren();
    const rows = [...seen.values()].sort((x, y) =>
      Number(x.blockNumber - y.blockNumber) || x.logIndex - y.logIndex);
    for (const log of rows.slice(-20)) {
      const li = document.createElement('li');
      const who = log.args.backer ?? log.args.creator;
      li.textContent = `block ${log.blockNumber}: ${log.eventName} ${formatEther(log.args.amount)} ETH, ${short(who)}`;
      list.append(li);
    }
  }
  
  function addLogs(logs) {
    for (const log of logs) seen.set(`${log.blockNumber}-${log.logIndex}`, log);
    renderEvents();
  }
  
  // Past events from the deployment block, then new ones as they arrive.
  async function startEvents() {
    const past = await publicClient.getContractEvents({
      address: cfg.address, abi: cfg.abi, fromBlock: BigInt(cfg.deployBlock), toBlock: 'latest',
    });
    addLogs(past);
    publicClient.watchContractEvent({
      address: cfg.address, abi: cfg.abi, pollingInterval: 1000,
      onLogs: async (logs) => { addLogs(logs); await refresh().catch(() => {}); },
      onError: (e) => say('banner', `Event watching stopped: ${explain(e)}`, 'bad'),
    });
  }
  
  function updateWalletView() {
    $('w-name').textContent = wallet ? wallet.name : 'not connected';
    $('w-account').textContent = account ?? '-';
    $('w-chain').textContent = walletChainId ?? '-';
    const wrongChain = Boolean(account) && walletChainId !== cfg.chainId;
    $('switch-chain').hidden = !wrongChain;
    if (wrongChain) say('banner', `The wallet is on chain ${walletChainId}, but this campaign is on chain ${cfg.chainId}. Switch the wallet before sending anything.`, 'bad');
    else if (account) say('banner', '');
    const ready = Boolean(account) && !wrongChain && !busy;
    for (const id of ['btn-contribute', 'btn-withdraw', 'btn-refund']) $(id).disabled = !ready;
  }
  
  $('switch-chain').addEventListener('click', async () => {
    try {
      await walletClient.switchChain({ id: cfg.chainId });
      walletChainId = await walletClient.getChainId();
      updateWalletView();
    } catch (err) {
      say('banner', `${explain(err)} If the wallet does not know this chain, add it in the wallet first.`, 'bad');
    }
  });
  
  async function useWallet(chosen) {
    wallet = chosen;
    walletClient = createWalletClient({ chain, transport: custom(chosen.provider) });
    // This is the only place the page asks for accounts, and only after a click.
    const [first] = await walletClient.requestAddresses();
    account = first;
    walletChainId = await walletClient.getChainId();
    chosen.provider.on?.('accountsChanged', async (list) => {
      account = list[0] ?? null;
      updateWalletView();
      await refresh().catch(() => {});
    });
    chosen.provider.on?.('chainChanged', (id) => { walletChainId = Number(id); updateWalletView(); });
    updateWalletView();
    await refresh();
  }
  
  async function connect(chosen) {
    try {
      await useWallet(chosen);
    } catch (err) {
      say('banner', explain(err), 'bad');
    }
  }
  
  // Wallet discovery (EIP-6963): wallets announce themselves; the page never assumes one.
  const found = new Map();
  function addWalletButton(detail) {
    if (found.has(detail.info.uuid)) return;
    found.set(detail.info.uuid, detail);
    const button = document.createElement('button');
    button.type = 'button';
    if (/^data:image\//.test(detail.info.icon)) {
      const img = document.createElement('img');
      img.src = detail.info.icon;
      img.alt = '';
      button.append(img);
    }
    button.append(document.createTextNode(`Connect ${detail.info.name}`));
    button.addEventListener('click', () => connect({ name: detail.info.name, provider: detail.provider }));
    $('wallets').append(button);
  }
  window.addEventListener('eip6963:announceProvider', (e) => addWalletButton(e.detail));
  window.dispatchEvent(new Event('eip6963:requestProvider'));
  // Older wallets only set window.ethereum, so offer it if nothing announces itself.
  setTimeout(() => {
    if (found.size === 0 && window.ethereum) {
      addWalletButton({
        info: { uuid: 'window.ethereum', name: 'browser wallet', icon: '', rdns: '' },
        provider: window.ethereum,
      });
    }
  }, 500);
  
  // Check first, then ask the wallet to sign, then wait for the chain to confirm.
  async function send(functionName, value) {
    if (busy) return;
    busy = true;
    updateWalletView();
    try {
      say('tx', 'Checking with the contract first...');
      const { request } = await publicClient.simulateContract({
        address: cfg.address, abi: cfg.abi, functionName, account, value,
      });
      say('tx', 'Waiting for you to confirm in the wallet...');
      const hash = await walletClient.writeContract(request);
      say('tx', `Pending: ${hash}`);
      const receipt = await publicClient.waitForTransactionReceipt({ hash });
      if (receipt.status === 'success') say('tx', `Confirmed in block ${receipt.blockNumber}: ${hash}`, 'ok');
      else say('tx', `The transaction was mined but failed: ${hash}`, 'bad');
      await refresh();
    } catch (err) {
      say('tx', explain(err), 'bad');
    } finally {
      busy = false;
      updateWalletView();
    }
  }
  
  $('contribute-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const text = $('amount').value.trim();
    if (!/^\d+(\.\d{1,18})?$/.test(text) || parseEther(text) === 0n) {
      say('tx', 'Enter an amount above zero, such as 0.5.', 'bad');
      return;
    }
    send('contribute', parseEther(text));
  });
  
  $('btn-withdraw').addEventListener('click', () => send('withdraw'));
  $('btn-refund').addEventListener('click', () => send('refund'));
  
  async function main() {
    cfg = await loadConfig();
    chain = {
      id: cfg.chainId, name: cfg.network ?? 'Campaign chain',
      nativeCurrency: { name: 'Ether', symbol: 'ETH', decimals: 18 },
      rpcUrls: { default: { http: [cfg.rpcUrl] } },
    };
    publicClient = createPublicClient({ chain, transport: http(cfg.rpcUrl) });
    const rpcChain = await publicClient.getChainId();
    if (rpcChain !== cfg.chainId) throw new Error(`The RPC node reports chain ${rpcChain}, not ${cfg.chainId}. Is Anvil running?`);
    $('v-address').textContent = cfg.address;
    $('v-chain').textContent = cfg.chainId;
    await refresh();
    await startEvents();
    updateWalletView();
  }
  
  main().catch((err) => say('banner', explain(err), 'bad'));