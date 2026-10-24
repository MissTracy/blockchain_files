// SPDX-License-Identifier: MIT
pragma solidity 0.8.37;

// Crowdfunding escrow, version 2: after the deadline the creator withdraws if the goal was met, otherwise each backer claims a refund.
contract Campaign {
    // Set once, at deployment, and never changeable afterwards.
    address public immutable creator;
    uint256 public immutable goal; // in wei
    uint256 public immutable deadline; // Unix time, in seconds

    // Change as the campaign runs.
    uint256 public totalRaised;
    bool public withdrawn;
    mapping(address backer => uint256 amount) public contributions;

    event Contributed(address indexed backer, uint256 amount);
    event Withdrawn(address indexed creator, uint256 amount);
    event Refunded(address indexed backer, uint256 amount);

    error InvalidGoal();
    error InvalidDuration();
    error ZeroContribution();
    error CampaignEnded(uint256 deadline);
    error CampaignStillRunning(uint256 deadline);
    error NotCreator();
    error GoalNotReached(uint256 totalRaised, uint256 goal);
    error GoalReached();
    error AlreadyWithdrawn();
    error NothingToRefund();
    error TransferFailed();

    modifier onlyCreator() {
        require(msg.sender == creator, NotCreator());
        _;
    }

    modifier afterDeadline() {
        require(block.timestamp >= deadline, CampaignStillRunning(deadline));
        _;
    }

    constructor(uint256 goal_, uint256 durationMinutes) {
        require(goal_ > 0, InvalidGoal());
        require(durationMinutes > 0, InvalidDuration());
        creator = msg.sender;
        goal = goal_;
        deadline = block.timestamp + durationMinutes * 1 minutes;
    }

    // Send ether to the campaign before the deadline.
    function contribute() external payable {
        require(msg.value > 0, ZeroContribution());
        require(block.timestamp < deadline, CampaignEnded(deadline));
        contributions[msg.sender] += msg.value;
        totalRaised += msg.value;
        emit Contributed(msg.sender, msg.value);
    }

    // The creator collects the funds after the deadline if the goal was met.
    function withdraw() external onlyCreator afterDeadline {
        // Checks
        require(totalRaised >= goal, GoalNotReached(totalRaised, goal));
        require(!withdrawn, AlreadyWithdrawn());
        // Effects
        withdrawn = true;
        uint256 amount = totalRaised;
        emit Withdrawn(creator, amount);
        // Interaction
        (bool ok,) = creator.call{value: amount}("");
        require(ok, TransferFailed());
    }

    // A backer takes their money back after the deadline if the goal was missed.
    function refund() external afterDeadline {
        // Checks
        require(totalRaised < goal, GoalReached());
        uint256 amount = contributions[msg.sender];
        require(amount > 0, NothingToRefund());
        // Effects: zero the balance before sending, so a second call finds nothing to refund
        contributions[msg.sender] = 0;
        emit Refunded(msg.sender, amount);
        // Interaction
        (bool ok,) = payable(msg.sender).call{value: amount}("");
        require(ok, TransferFailed());
    }
}
