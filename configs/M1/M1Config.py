from caches import *

import m5
from m5.objects import *

"""
Wikipedia: https://en.wikipedia.org/wiki/Apple_M1#:~:text=M1%20Pro%20and%20M1%20Max,-The%20M1%20Pro&text=The%20high%2Dperformance%20cores%20are,are%20clocked%20at%202064%20MHz.
"""
system = System()

# Set the clock frequency of the system (and all of its children)
system.clk_domain = SrcClockDomain()
system.clk_domain.clock = "3.2GHz"  # Wikipedia, max CPU clock rate
system.clk_domain.voltage_domain = VoltageDomain()

# Set up the system
system.mem_mode = "timing"
system.mem_ranges = [AddrRange("512MB")]

# Create CPU
system.cpu = O3CPU()

# Create L1 caches
system.cpu.icache = L1ICache()
system.cpu.dcache = L1DCache()

# Connect L1 caches to CPU
system.cpu.icache.connectCPU(system.cpu)
system.cpu.dcache.connectCPU(system.cpu)

# Create a memory bus
system.l2bus = L2XBar()

# Connect L2 memory bus to L1 caches
system.cpu.icache.connectBus(system.l2bus)
system.cpu.dcache.connectBus(system.l2bus)

# Create L2 cache
system.l2cache = L2Cache()
system.l2cache.connectCPUSideBus(system.l2bus)
system.membus = SystemXBar()
system.l2cache.connectMemSideBus(system.membus)

# create the interrupt controller for the CPU and connect to the membus
system.cpu.createInterruptController()

# Connect the system up to the membus
system.system_port = system.membus.cpu_side_ports

# Create a DDR4 memory controller and connect it to the membus
system.mem_ctrl = MemCtrl()
system.mem_ctrl.dram = (
    DDR4_2400_8x8()
)  # Wikipedia, M1 uses LPDDR4X, the closest I found was DDR4
system.mem_ctrl.dram.range = system.mem_ranges[0]
system.mem_ctrl.port = system.membus.mem_side_ports

binary = "cpu_tests/benchmarks/bin/arm/Bubblesort"

# for gem5 V21 and beyond
system.workload = SEWorkload.init_compatible(binary)

process = Process()
process.cmd = [binary]
system.cpu.workload = process
system.cpu.createThreads()


root = Root(full_system=False, system=system)
m5.instantiate()

print("Beginning simulation!")
exit_event = m5.simulate()

print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")
