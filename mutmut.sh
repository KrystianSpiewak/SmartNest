#!/bin/bash
# SmartNest Mutation Testing Workflow
# Run from WSL: ./mutmut.sh [sync|run|results|html|report|all]

set -e

WINDOWS_PROJECT="/mnt/d/Programowanie/College/Champlain/SDEV435/SmartNest"
WSL_PROJECT="$HOME/smartnest-project"
VENV="$HOME/smartnest-venv"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

error() {
    echo -e "${RED}Error: $1${NC}" >&2
    exit 1
}

info() {
    echo -e "${GREEN}$1${NC}"
}

warn() {
    echo -e "${YELLOW}$1${NC}"
}

check_venv() {
    if [ ! -d "$VENV" ]; then
        error "Virtual environment not found at $VENV. Run setup first."
    fi
}

sync_project() {
    info "Syncing project from Windows to WSL..."
    rsync -av --delete "$WINDOWS_PROJECT/" "$WSL_PROJECT/" \
        --exclude '.venv' \
        --exclude '.venv-wsl' \
        --exclude '__pycache__' \
        --exclude '.git' \
        --exclude 'mutmut-report' \
        --exclude 'htmlcov' \
        --exclude '.mutmut-cache' \
        --exclude 'mutants'
    info "Sync complete."
}

run_mutmut() {
    check_venv
    info "Running mutation tests..."
    cd "$WSL_PROJECT"
    source "$VENV/bin/activate"
    mutmut run
    info "Mutation testing complete."
}

show_results() {
    check_venv
    cd "$WSL_PROJECT"
    source "$VENV/bin/activate"
    mutmut results
    echo ""
    warn "To list surviving mutants: ./mutmut.sh list"
    warn "To view mutant details: ./mutmut.sh show <full-mutant-id>"
}

list_mutants() {
    check_venv
    cd "$WSL_PROJECT"
    source "$VENV/bin/activate"
    echo ""
    info "Surviving and timeout mutants:"
    echo ""
    mutmut results | grep -E "(survived|timeout)" | nl -v 1 -w 3 -s ". "
    echo ""
    warn "Use the FULL mutant ID with: ./mutmut.sh show <full-id>"
    warn "Example: ./mutmut.sh show backend.mqtt.client.xǁSmartNestMQTTClientǁ__init____mutmut_11"
}

analyze_mutants() {
    check_venv
    cd "$WSL_PROJECT"
    source "$VENV/bin/activate"
    
    if [ ! -f "scripts/analyze_mutants.py" ]; then
        error "Analyzer script not found. Make sure scripts/analyze_mutants.py exists."
    fi
    
    python3 scripts/analyze_mutants.py
}

generate_report() {
    check_venv
    cd "$WSL_PROJECT"
    source "$VENV/bin/activate"
    
    info "Generating detailed mutation report..."
    
    # Create report directory
    mkdir -p reports
    
    # Generate comprehensive report
    {
        echo "====================================================================="
        echo "SmartNest Mutation Testing Report"
        echo "Generated: $(date)"
        echo "====================================================================="
        echo ""
        mutmut results
        echo ""
        echo "====================================================================="
        echo "DETAILED MUTANT LIST"
        echo "====================================================================="
        echo ""
        mutmut results | grep -E "(survived|timeout)"
    } > reports/mutation_report.txt
    
    info "Report generated at reports/mutation_report.txt"
}

sync_report() {
    if [ ! -f "$WSL_PROJECT/reports/mutation_report.txt" ]; then
        error "Report not found. Run './mutmut.sh report' first."
    fi
    
    info "Copying report to Windows..."
    mkdir -p "$WINDOWS_PROJECT/reports"
    cp "$WSL_PROJECT/reports/mutation_report.txt" "$WINDOWS_PROJECT/reports/"
    
    info "Report synced to reports/mutation_report.txt"
    warn "You can now view the report in Windows or commit it to git"
}

show_mutant() {
    if [ -z "$1" ]; then
        error "Usage: ./mutmut.sh show <full-mutant-id>"
    fi
    check_venv
    cd "$WSL_PROJECT"
    source "$VENV/bin/activate"
    mutmut show "$1"
}

apply_mutant() {
    if [ -z "$1" ]; then
        error "Usage: ./mutmut.sh apply <full-mutant-id>"
    fi
    check_venv
    cd "$WSL_PROJECT"
    source "$VENV/bin/activate"
    info "Applying mutant to see code changes..."
    mutmut apply "$1"
    warn "Mutant applied. View the changed files, then revert with: git checkout ."
}

show_survivors() {
    check_venv
    cd "$WSL_PROJECT"
    source "$VENV/bin/activate"
    
    local max_show="${1:-10}"
    
    info "Collecting surviving mutants..."
    local survivors=$(mutmut results | grep -E "(survived|timeout)" | head -n "$max_show")
    local count=$(echo "$survivors" | wc -l)
    
    info "Showing first $count surviving mutants with diffs:"
    echo ""
    
    local i=1
    while IFS= read -r line; do
        # Extract mutant ID (everything before the colon)
        local mutant_id=$(echo "$line" | sed 's/:.*//' | xargs)
        
        echo -e "${GREEN}[$i/$count] $mutant_id${NC}"
        echo "─────────────────────────────────────────────────────────────"
        mutmut show "$mutant_id" 2>&1 || echo "  (Could not show diff)"
        echo ""
        ((i++))
    done <<< "$survivors"
    
    if [ "$count" -eq "$max_show" ]; then
        warn "Showing only first $max_show. Use: ./mutmut.sh show-survivors <number> for more"
    fi
    
    info "To apply a specific mutant: ./mutmut.sh apply <mutant-id>"
}

show_detailed_report() {
    check_venv
    cd "$WSL_PROJECT"
    source "$VENV/bin/activate"
    
    info "Generating detailed report with mutant diffs..."
    
    mkdir -p reports
    
    local report_file="reports/mutation_report_detailed.txt"
    
    {
        echo "====================================================================="
        echo "SmartNest Detailed Mutation Testing Report"
        echo "Generated: $(date)"
        echo "====================================================================="
        echo ""
        mutmut results
        echo ""
        echo "====================================================================="
        echo "SURVIVING MUTANTS WITH DIFFS"
        echo "====================================================================="
        echo ""
        
        local survivors=$(mutmut results | grep -E "(survived|timeout)")
        local i=1
        while IFS= read -r line; do
            local mutant_id=$(echo "$line" | sed 's/:.*//' | xargs)
            echo "[$i] $mutant_id"
            echo "─────────────────────────────────────────────────────────────"
            mutmut show "$mutant_id" 2>&1 || echo "  (Could not show diff)"
            echo ""
            echo ""
            ((i++))
        done <<< "$survivors"
        
    } > "$report_file"
    
    info "Detailed report generated at $report_file"
    
    # Sync to Windows
    mkdir -p "$WINDOWS_PROJECT/reports"
    cp "$report_file" "$WINDOWS_PROJECT/reports/"
    info "Report synced to Windows at reports/mutation_report_detailed.txt"
}

run_all() {
    sync_project
    run_mutmut
    show_results
    generate_report
    sync_report
    info "Complete! Summary: reports/mutation_report.txt"
    info "For diffs run: ./mutmut.sh detailed-report"
}

# Main script
case "${1:-all}" in
    sync)
        sync_project
        ;;
    run)
        run_mutmut
        ;;
    results)
        show_results
        ;;
    list)
        list_mutants
        ;;
    analyze)
        analyze_mutants
        ;;
    report)
        generate_report
        ;;
    sync-report)
        sync_report
        ;;
    show)
        show_mutant "$2"
        ;;
    apply)
        apply_mutant "$2"
        ;;
    show-survivors)
        show_survivors "$2"
        ;;
    detailed-report)
        show_detailed_report
        ;;
    all)
        run_all
        ;;
    *)
        echo "Usage: $0 [sync|run|results|list|analyze|report|sync-report|show|apply|show-survivors|detailed-report|all]"
        echo ""
        echo "Commands:"
        echo "  sync              - Sync project from Windows to WSL"
        echo "  run               - Run mutation testing"
        echo "  results           - Show mutation testing summary"
        echo "  list              - List all surviving mutants with numbers"
        echo "  analyze           - Categorize mutants by priority"
        echo "  report            - Generate summary text report"
        echo "  sync-report       - Copy report back to Windows"
        echo "  show <full-id>    - Show diff for specific mutant"
        echo "  apply <full-id>   - Apply mutant to see actual code changes"
        echo "  show-survivors [n] - Show diffs for first n survivors (default 10)"
        echo "  detailed-report   - Generate report with ALL mutant diffs"
        echo "  all               - Run full pipeline (default)"
        echo ""
        echo "Workflow:"
        echo "  1. ./mutmut.sh all                    # Run tests + generate report"
        echo "  2. Check reports/mutation_report.txt in Windows"
        echo "  3. ./mutmut.sh show-survivors 5       # View first 5 surviving mutants with diffs"
        echo "  4. ./mutmut.sh detailed-report        # Generate full report with all diffs"
        echo "  5. ./mutmut.sh apply <id>             # Apply mutant (then sync to revert)"
        exit 1
        ;;
esac
