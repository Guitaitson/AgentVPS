#!/bin/bash
# VPS-Agent Self-Improvement Script
# Allows the agent to update itself and create releases

set -e

VERSION_FILE="core/__version__.py"
GIT_REPO="git@github.com:SEU_USUARIO/vps-agent.git"
BRANCH="main"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}🧠 VPS-Agent Self-Improvement${NC}"
echo "======================================"

# Get current version
get_version() {
    grep "__version__" "$VERSION_FILE" | cut -d'"' -f2
}

# Update version
update_version() {
    local new_version="$1"
    sed -i "s/__version__ = \".*\"/__version__ = \"$new_version\"/" "$VERSION_FILE"
    echo -e "${GREEN}Version updated to $new_version${NC}"
}

# Check for updates
check_updates() {
    echo -e "${YELLOW}Checking for updates...${NC}"
    curl -s "$UPDATE_CHECK_URL" | grep -o '"tag_name": "[^"]*' | cut -d'"' -f4
}

# Create backup
create_backup() {
    local backup_dir="backups/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_dir"
    cp -r . "$backup_dir/" --exclude='.git' --exclude='backups' --exclude='venv'
    echo -e "${GREEN}Backup created at $backup_dir${NC}"
    echo "$backup_dir"
}

# Git operations
git_commit() {
    local message="$1"
    git add -A
    git commit -m "$message"
    echo -e "${GREEN}Committed: $message${NC}"
}

git_push() {
    git push origin "$BRANCH"
    echo -e "${GREEN}Pushed to $BRANCH${NC}"
}

# Generate changelog
generate_changelog() {
    local version="$1"
    echo "# Changelog" > CHANGELOG.md
    echo "" >> CHANGELOG.md
    echo "## $version ($(date +%Y-%m-%d))" >> CHANGELOG.md
    echo "" >> CHANGELOG.md
    git log --pretty="- %s" --since="30 days ago" >> CHANGELOG.md
    echo -e "${GREEN}Changelog generated${NC}"
}

# Create release
create_release() {
    local version="$1"
    local description="$2"
    
    echo -e "${YELLOW}Creating release $version...${NC}"
    
    # Commit version update
    git_commit "Release: $version"
    
    # Tag
    git tag -a "v$version" -m "Release $version"
    
    # Push
    git_push
    git push origin "v$version"
    
    echo -e "${GREEN}Release v$version created!${NC}"
    echo "URL: $RELEASES_URL"
}

# Self-update
self_update() {
    echo -e "${YELLOW}Self-update initiated...${NC}"
    
    # Create backup
    create_backup
    
    # Pull latest
    git pull origin "$BRANCH"
    
    # Restart services
    docker compose -f configs/docker-compose.core.yml restart
    
    echo -e "${GREEN}Self-update complete!${NC}"
}

# Analyze and improve
analyze_improve() {
    echo -e "${YELLOW}Analyzing code for improvements...${NC}"
    
    # Check for TODO comments
    local todos=$(grep -r "TODO\|FIXME" --include="*.py" . | wc -l)
    echo "TODO/FIXME comments found: $todos"
    
    # Check code complexity (basic)
    echo "Python files: $(find . -name "*.py" | wc -l)"
    echo "Lines of code: $(find . -name "*.py" -exec wc -l {} + | tail -1)"
    
    # Suggest improvements
    echo -e "${YELLOW}Suggested improvements:${NC}"
    echo "1. Review TODO comments"
    echo "2. Update documentation"
    echo "3. Run security scan"
    echo "4. Test all endpoints"
}

# Deploy to new VPS
deploy_new() {
    local target_vps="$1"
    echo -e "${YELLOW}Deploying to new VPS: $target_vps${NC}"
    
    # Create deployment package
    tar -czf vps-agent-deploy.tar.gz \
        --exclude='.git' \
        --exclude='backups' \
        --exclude='venv' \
        --exclude='__pycache__' \
        --exclude='*.log' \
        .
    
    # Copy and deploy
    ssh "$target_vps" "mkdir -p /opt/vps-agent && tar -xzf - -C /opt/vps-agent"
    
    echo -e "${GREEN}Deployed to $target_vps${NC}"
}

# Menu
show_menu() {
    echo ""
    echo "Options:"
    echo "  1) Check version"
    echo "  2) Check for updates"
    echo "  3) Create backup"
    echo "  4) Analyze and improve"
    echo "  5) Create release"
    echo "  6) Self-update"
    echo "  7) Deploy to new VPS"
    echo "  0) Exit"
    echo ""
}

# Main
main() {
    local action="${1:-menu}"
    
    case $action in
        version)
            echo "Current version: $(get_version)"
            ;;
        update)
            self_update
            ;;
        backup)
            create_backup
            ;;
        analyze)
            analyze_improve
            ;;
        release)
            update_version "${2:-$(get_version)}"
            generate_changelog "${2:-$(get_version)}"
            create_release "${2:-$(get_version)}" "${3:-Auto-generated release}"
            ;;
        deploy)
            deploy_new "$2"
            ;;
        menu|*)
            show_menu
            ;;
    esac
}

main "$@"
