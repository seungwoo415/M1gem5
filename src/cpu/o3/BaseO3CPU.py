# Copyright (c) 2016, 2019 ARM Limited
# All rights reserved.
#
# The license below extends only to copyright in the software and shall
# not be construed as granting a license to any other intellectual
# property including but not limited to intellectual property relating
# to a hardware implementation of the functionality of the software
# licensed hereunder.  You may use the software subject to the license
# terms below provided that you ensure that this notice is replicated
# unmodified and in its entirety in all distributions of the software,
# modified or unmodified, in source code or in binary form.
#
# Copyright (c) 2005-2007 The Regents of The University of Michigan
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met: redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer;
# redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution;
# neither the name of the copyright holders nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from m5.defines import buildEnv
from m5.objects.BaseCPU import BaseCPU

# from m5.objects.O3Checker import O3Checker
from m5.objects.BranchPredictor import *
from m5.objects.FUPool import *
from m5.params import *
from m5.proxy import *


class SMTFetchPolicy(ScopedEnum):
    vals = ["RoundRobin", "Branch", "IQCount", "LSQCount"]


class SMTQueuePolicy(ScopedEnum):
    vals = ["Dynamic", "Partitioned", "Threshold"]


class CommitPolicy(ScopedEnum):
    vals = ["RoundRobin", "OldestReady"]


"""
firestorm p core

Dougall Johnson(DJ): https://dougallj.github.io/applecpu/firestorm.html
Maynard Handley(MH) (Vol1: M1 Explainer) (Vol4: Instruction Fetch): https://github.com/name99-org/AArch64-Explore
Dougall Johnson(DJ) blog: https://dougallj.wordpress.com/2021/04/08/apple-m1-load-and-store-queue-measurements/
S2C paper: https://www.usenix.org/system/files/usenixsecurity23-yu-jiyong.pdf

"""


class BaseO3CPU(BaseCPU):
    type = "BaseO3CPU"
    cxx_class = "gem5::o3::CPU"
    cxx_header = "cpu/o3/dyn_inst.hh"

    @classmethod
    def memory_mode(cls):
        return timing

    @classmethod
    def require_caches(cls):
        return true

    @classmethod
    def support_take_over(cls):
        return true

    activity = Param.Unsigned(0, "Initial count")

    cacheStorePorts = Param.Unsigned(
        200,
        "Cache Ports. "
        "Constrains stores only. Loads are constrained by load FUs.",
    )

    cacheLoadPorts = Param.Unsigned(
        200,
        "Validation Ports. "
        "Constrains validations only. Loads are constrained by load FUs.",
    )

    decodeToFetchDelay = Param.Cycles(1, "Decode to fetch delay")
    renameToFetchDelay = Param.Cycles(1, "Rename to fetch delay")
    iewToFetchDelay = Param.Cycles(
        1, "Issue/Execute/Writeback to fetch " "delay"
    )
    commitToFetchDelay = Param.Cycles(1, "Commit to detch delay")
    fetchWidth = Param.Unsigned(
        8, "Fetch width"
    )  # DJ, "pipeline overview" diagram shows decode width is 8 --> reasonable to have a fetch width that is similar
    fetchBufferSize = Param.Unsigned(64, "Fetch buffer size in bytes")
    fetchQueueSize = Param.Unsigned(
        32, "Fetch queue size in micro-ops per-thread"
    )
    renameToDecodeDelay = Param.Cycles(1, "Rename to decode delay")
    iewToDecodeDelay = Param.Cycles(
        1, "Issue/Execute/Writeback to decode " "delay"
    )
    commitToDecodeDelay = Param.Cycles(1, "Commit to decode delay")
    fetchToDecodeDelay = Param.Cycles(1, "Fetch to decode delay")
    decodeWidth = Param.Unsigned(
        8, "Decode width"
    )  # DJ, "pipeline overview" diagram shows decode width is 8
    iewToRenameDelay = Param.Cycles(
        1, "Issue/Execute/Writeback to rename " "delay"
    )
    commitToRenameDelay = Param.Cycles(1, "Commit to rename delay")
    decodeToRenameDelay = Param.Cycles(1, "Decode to rename delay")
    renameWidth = Param.Unsigned(
        8, "Rename width"
    )  # DJ, "pipeline overview" diagram shows "Map and Rename" takes in 8 uops
    # MH page 30, rename and decode has same width
    commitToIEWDelay = Param.Cycles(
        1, "Commit to Issue/Execute/Writeback delay"
    )
    renameToIEWDelay = Param.Cycles(
        2, "Rename to Issue/Execute/Writeback delay"
    )
    issueToExecuteDelay = Param.Cycles(
        1, "Issue to execute delay (internal to the IEW stage)"
    )
    dispatchWidth = Param.Unsigned(
        8, "Dispatch width"
    )  # DJ,  "pipeline overview" diagram has all dispatch queue widths are set to 8 uops
    issueWidth = Param.Unsigned(
        1, "Issue width"
    )  # DJ, "pipeline overview" diagram has all schedulers issue 1 uops
    wbWidth = Param.Unsigned(
        1, "Writeback width"
    )  # Not specified in DJ nor MH but assumed that it is the same as the issue width
    fuPool = Param.FUPool(
        DefaultFUPool(), "Functional Unit pool"
    )  # checked FuncUnitConfig.py file and count is relatively the same as the number of functional units in dj

    iewToCommitDelay = Param.Cycles(
        1, "Issue/Execute/Writeback to commit delay"
    )
    renameToROBDelay = Param.Cycles(1, "Rename to reorder buffer delay")
    commitWidth = Param.Unsigned(
        7, "Commit width"
    )  # DJ, "Completion, and the Reorder Buffer(ROB)" section mentions uops are coalesces into retire groups up to 7 uops
    squashWidth = Param.Unsigned(8, "Squash width")
    trapLatency = Param.Cycles(13, "Trap latency")
    fetchTrapLatency = Param.Cycles(1, "Fetch trap latency")

    backComSize = Param.Unsigned(
        20, "Time buffer size for backwards communication"
    )  # increased time buffer to 20 as increase in size of other stages require a larger time buffer size
    forwardComSize = Param.Unsigned(
        20, "Time buffer size for forward communication"
    )

    LQEntries = Param.Unsigned(
        130, "Number of load queue entries"
    )  # DJ Blog, "Fighting Stores with Square-Roots" section mentions load queues were measured to have 130 entries
    SQEntries = Param.Unsigned(
        60, "Number of store queue entries"
    )  # DJ Blog, "Fighting Stores with Square-Roots" section mentions store queues were measured to have 60 entries
    LSQDepCheckShift = Param.Unsigned(
        4, "Number of places to shift addr before check"
    )
    LSQCheckLoads = Param.Bool(
        True,
        "Should dependency violations be checked for "
        "loads & stores or just stores",
    )
    store_set_clear_period = Param.Unsigned(
        250000,
        "Number of load/store insts before the dep predictor "
        "should be invalidated",
    )
    LFSTSize = Param.Unsigned(1024, "Last fetched store table size")
    SSITSize = Param.Unsigned(1024, "Store set ID table size")

    numRobs = Param.Unsigned(
        1, "Number of Reorder Buffers"
    )  # DJ, "Completion, and the Reorder Buffer(ROB)" mentions that Firestorm uses an unconventional reorder buffer

    numPhysIntRegs = Param.Unsigned(
        380, "Number of physical integer registers"
    )  # DJ, "Other limits" section mentions the integer physical register file size is 380-394
    numPhysFloatRegs = Param.Unsigned(
        216, "Number of physical floating point registers"
    )  # DJ, "Other limits" section mentions FP/SIMD physical register file is 432 --> divided into 2
    numPhysVecRegs = Param.Unsigned(
        216, "Number of physical vector registers"
    )  # DJ, "Other limits" section mentions FP/SIMD physical register file is 432 --> divided into 2
    numPhysVecPredRegs = Param.Unsigned(
        32, "Number of physical predicate registers"
    )
    numPhysMatRegs = Param.Unsigned(2, "Number of physical matrix registers")
    numPhysCCRegs = Param.Unsigned(
        128, "Number of physical cc registers"
    )  # DJ, "Other limits" section mentions flags physical register file size is 128
    numIQEntries = Param.Unsigned(
        120, "Number of instruction queue entries"
    )  # MH Vol4 page 5, mentions 120 entries for the instruction queue
    numROBEntries = Param.Unsigned(
        330, "Number of reorder buffer entries"
    )  # MH Vol1 page 113, mentions ROB has 330 rows with 7 instructions each, but only one slot is used

    smtNumFetchingThreads = Param.Unsigned(
        1, "SMT Number of Fetching Threads"
    )  # S2C paper page 4, mentions m1 doesn't implement smt --> left as default
    smtFetchPolicy = Param.SMTFetchPolicy("RoundRobin", "SMT Fetch policy")
    smtLSQPolicy = Param.SMTQueuePolicy(
        "Partitioned", "SMT LSQ Sharing Policy"
    )
    smtLSQThreshold = Param.Int(100, "SMT LSQ Threshold Sharing Parameter")
    smtIQPolicy = Param.SMTQueuePolicy("Partitioned", "SMT IQ Sharing Policy")
    smtIQThreshold = Param.Int(100, "SMT IQ Threshold Sharing Parameter")
    smtROBPolicy = Param.SMTQueuePolicy(
        "Partitioned", "SMT ROB Sharing Policy"
    )
    smtROBThreshold = Param.Int(100, "SMT ROB Threshold Sharing Parameter")
    smtCommitPolicy = Param.CommitPolicy("RoundRobin", "SMT Commit Policy")

    branchPred = Param.BranchPredictor(
        TAGE(
            numThreads=Parent.numThreads
        ),  # MH Vol4 page 53, explains about a reduced power TAGE branch predictor
        "Branch Predictor",
    )
    needsTSO = Param.Bool(False, "Enable TSO Memory model")
