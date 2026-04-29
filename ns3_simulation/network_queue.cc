// ns3_simulation/network_queue.cc
//
// TOPOLOGY:
//
//   [Sender Node 0] ---link--- [Router Node 1] ---link--- [Receiver Node 2]
//                               ^
//                               This is your M/M/1 queue
//                               Buffer here = Lq
//                               Delay here  = Wq
//
// Packets arrive at Node 0 via Poisson process (OnOff application)
// Node 1 is the bottleneck router — the queue forms here
// Node 2 receives packets and logs statistics

#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/applications-module.h"
#include "ns3/flow-monitor-module.h"
#include "ns3/traffic-control-module.h"

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("NetworkQueueSim");

// Global counters — written to file for Python to read
uint32_t g_packetsReceived = 0;
uint32_t g_packetsDropped  = 0;
double   g_totalDelay      = 0.0;

void PacketReceived(Ptr<const Packet> packet, const Address& addr) {
    g_packetsReceived++;
}

int main(int argc, char *argv[]) {

    // ── Parameters (match your analytical model) ──────────────────
    double  simTime      = 10.0;       // seconds
    double  arrivalRate  = 100.0;      // packets/sec  (lambda)
    uint32_t packetSize  = 1000;       // bytes
    // Link bandwidth → service rate μ = bandwidth / packetSize
    // At 1.2 Mbps and 1000-byte packets: μ = 1200000/8000 = 150 pkt/s
    std::string linkBandwidth = "1.2Mbps";
    std::string linkDelay     = "1ms";
    uint32_t    bufferSize    = 100;   // max packets in queue
    uint32_t    numServers    = 1;     // K — change for M/M/K

    CommandLine cmd;
    cmd.AddValue("arrivalRate",   "Packet arrival rate (pkt/s)", arrivalRate);
    cmd.AddValue("linkBandwidth", "Link bandwidth",              linkBandwidth);
    cmd.AddValue("bufferSize",    "Router buffer size (packets)",bufferSize);
    cmd.AddValue("numServers",    "Number of parallel links (K)",numServers);
    cmd.AddValue("simTime",       "Simulation duration (s)",     simTime);
    cmd.Parse(argc, argv);

    // ── Build topology ────────────────────────────────────────────
    NodeContainer nodes;
    nodes.Create(2 + numServers);   // sender + K routers + receiver

    // Sender → Router link (high bandwidth — not the bottleneck)
    PointToPointHelper accessLink;
    accessLink.SetDeviceAttribute("DataRate", StringValue("100Mbps"));
    accessLink.SetChannelAttribute("Delay", StringValue("0ms"));

    // Router → Receiver link (bottleneck — this IS the M/M/1 queue)
    PointToPointHelper bottleneck;
    bottleneck.SetDeviceAttribute("DataRate", StringValue(linkBandwidth));
    bottleneck.SetChannelAttribute("Delay",   StringValue(linkDelay));
    // Set queue discipline — DropTail = FCFS (first come first served)
    bottleneck.SetQueue("ns3::DropTailQueue",
                        "MaxSize", StringValue(
                            std::to_string(bufferSize) + "p"));

    // Install internet stack
    InternetStackHelper internet;
    internet.InstallAll();

    // Connect sender to first router
    NetDeviceContainer d0 = accessLink.Install(nodes.Get(0), nodes.Get(1));

    // Connect router(s) to receiver
    NetDeviceContainer d1 = bottleneck.Install(nodes.Get(1), nodes.Get(2));

    // Assign IP addresses
    Ipv4AddressHelper ipv4;
    ipv4.SetBase("10.1.1.0", "255.255.255.0");
    ipv4.Assign(d0);
    ipv4.SetBase("10.1.2.0", "255.255.255.0");
    Ipv4InterfaceContainer iface = ipv4.Assign(d1);
    Ipv4GlobalRoutingHelper::PopulateRoutingTables();

    // ── Traffic source — Poisson packet arrivals ──────────────────
    // OnOff application with exponential on/off times models
    // a Poisson arrival process when packet size is fixed.
    uint16_t port = 9;
    OnOffHelper onoff("ns3::UdpSocketFactory",
                      InetSocketAddress(iface.GetAddress(1), port));

    // Mean ON time controls arrival rate:
    // mean_on = packetSize_bits / (arrivalRate * packetSize_bits) = 1/arrivalRate
    double meanOnTime = 1.0 / arrivalRate;
    onoff.SetAttribute("OnTime",
        StringValue("ns3::ExponentialRandomVariable[Mean=" +
                    std::to_string(meanOnTime) + "]"));
    onoff.SetAttribute("OffTime",
        StringValue("ns3::ConstantRandomVariable[Constant=0.0]"));
    onoff.SetAttribute("DataRate",
        DataRateValue(DataRate(
            (uint64_t)(arrivalRate * packetSize * 8))));
    onoff.SetAttribute("PacketSize", UintegerValue(packetSize));

    ApplicationContainer apps = onoff.Install(nodes.Get(0));
    apps.Start(Seconds(0.1));
    apps.Stop(Seconds(simTime));

    // ── Packet sink (receiver) ────────────────────────────────────
    PacketSinkHelper sink("ns3::UdpSocketFactory",
                          InetSocketAddress(Ipv4Address::GetAny(), port));
    ApplicationContainer sinkApps = sink.Install(nodes.Get(2));
    sinkApps.Start(Seconds(0.0));
    sinkApps.Stop(Seconds(simTime + 1));

    // ── Flow monitor (collects delay, throughput, loss stats) ─────
    FlowMonitorHelper flowmon;
    Ptr<FlowMonitor> monitor = flowmon.InstallAll();

    // ── Run simulation ────────────────────────────────────────────
    NS_LOG_UNCOND("Running NS3 Network Queue Simulation...");
    NS_LOG_UNCOND("lambda = " << arrivalRate << " pkt/s");
    NS_LOG_UNCOND("K = " << numServers << " server(s)");

    Simulator::Stop(Seconds(simTime + 2));
    Simulator::Run();

    // ── Collect and print results ─────────────────────────────────
    monitor->CheckForLostPackets();
    Ptr<Ipv4FlowClassifier> classifier =
        DynamicCast<Ipv4FlowClassifier>(flowmon.GetClassifier());
    FlowMonitor::FlowStatsContainer stats = monitor->GetFlowStats();

    double totalDelay    = 0.0;
    uint64_t rxPackets   = 0;
    uint64_t txPackets   = 0;
    uint64_t lostPackets = 0;

    for (auto& flow : stats) {
        totalDelay  += flow.second.delaySum.GetSeconds();
        rxPackets   += flow.second.rxPackets;
        txPackets   += flow.second.txPackets;
        lostPackets += (flow.second.txPackets - flow.second.rxPackets);
    }

    double avgDelay  = (rxPackets > 0) ? (totalDelay / rxPackets) : 0;
    double lossRate  = (txPackets > 0) ?
                       ((double)lostPackets / txPackets * 100) : 0;

    // Print in format Python bridge can parse
    std::cout << "NS3_RESULT:avg_delay_ms="
              << avgDelay * 1000 << std::endl;
    std::cout << "NS3_RESULT:rx_packets="
              << rxPackets << std::endl;
    std::cout << "NS3_RESULT:tx_packets="
              << txPackets << std::endl;
    std::cout << "NS3_RESULT:loss_rate_pct="
              << lossRate << std::endl;
    std::cout << "NS3_RESULT:throughput_kbps="
              << (rxPackets * packetSize * 8) / (simTime * 1000)
              << std::endl;

    Simulator::Destroy();
    return 0;
}