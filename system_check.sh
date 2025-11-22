#!/bin/bash
# System capacity and maintenance check

echo "=========================================="
echo "   SYSTEM CAPACITY CHECK"
echo "=========================================="
echo ""

# CPU info
echo "CPU Information:"
sysctl -n machdep.cpu.brand_string
echo "CPU Cores: $(sysctl -n hw.ncpu)"
echo "Physical Cores: $(sysctl -n hw.physicalcpu)"
echo ""

# Memory info
echo "Memory Information:"
total_mem=$(sysctl -n hw.memsize)
total_gb=$((total_mem / 1024 / 1024 / 1024))
echo "Total RAM: ${total_gb} GB"
echo ""
vm_stat | perl -ne '/page size of (\d+)/ and $size=$1; /Pages\s+([^:]+)[^\d]+(\d+)/ and printf("%-16s % 16.2f GB\n", "$1:", $2 * $size / 1073741824);'
echo ""

# Disk info
echo "Disk Space:"
df -h / | tail -1 | awk '{printf "System Disk: %s used / %s total (%s free)\n", $3, $2, $4}'
df -h "/Volumes/My Book" | tail -1 | awk '{printf "External Drive: %s used / %s total (%s free)\n", $3, $2, $4}'
echo ""

# Current load
echo "Current System Load:"
uptime
echo ""

# Check for parallel processing capacity
echo "Parallel Processing Assessment:"
cores=$(sysctl -n hw.physicalcpu)
if [ $cores -ge 6 ]; then
    echo "✅ EXCELLENT: $cores cores - Can easily handle 3-4 parallel processes"
elif [ $cores -ge 4 ]; then
    echo "✅ GOOD: $cores cores - Can handle 3 parallel processes"
else
    echo "⚠️  LIMITED: $cores cores - Recommend 2 parallel processes max"
fi
echo ""

# Memory for parallel
free_mem_gb=$((total_gb - 8))  # Reserve 8GB for system
processes_supported=$((free_mem_gb / 2))  # 2GB per process
echo "Memory Available for Processing: ~${free_mem_gb} GB"
echo "Processes Supported (2GB each): ~${processes_supported}"
echo ""

# Thermal check (if available)
echo "Temperature Check:"
if command -v osx-cpu-temp &> /dev/null; then
    osx-cpu-temp
else
    echo "  (Install osx-cpu-temp for thermal monitoring)"
fi
echo ""

# Recommendation
echo "=========================================="
echo "   RECOMMENDATION"
echo "=========================================="
if [ $cores -ge 4 ] && [ $total_gb -ge 16 ]; then
    echo "✅ System can handle 3 PARALLEL processes"
    echo "✅ Recommended: Process all 3 directories simultaneously"
else
    echo "⚠️  System limited - recommend 2 processes maximum"
fi
echo ""

