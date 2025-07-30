#!/bin/bash

# Journal Grabber - Podman/Docker Management Script

set -e

CONTAINER_NAME="journalgrabber"
IMAGE_NAME="journalgrabber:latest"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if podman is available, fallback to docker
detect_container_runtime() {
    if command -v podman &> /dev/null; then
        RUNTIME="podman"
    elif command -v docker &> /dev/null; then
        RUNTIME="docker"
    else
        print_error "Neither podman nor docker found. Please install one of them."
        exit 1
    fi
    print_status "Using container runtime: $RUNTIME"
}

build_image() {
    print_status "Building Journal Grabber image..."
    $RUNTIME build -t $IMAGE_NAME .
    print_success "Image built successfully!"
}

start_container() {
    print_status "Starting Journal Grabber container..."
    
    # Create necessary directories
    mkdir -p downloads data
    
    # Stop existing container if running
    if $RUNTIME ps -q -f name=$CONTAINER_NAME | grep -q .; then
        print_warning "Stopping existing container..."
        $RUNTIME stop $CONTAINER_NAME
        $RUNTIME rm $CONTAINER_NAME
    fi
    
    # Start new container
    $RUNTIME run -d \
        --name $CONTAINER_NAME \
        -p 5000:5000 \
        -v "$(pwd)/downloads:/app/downloads:Z" \
        -v "$(pwd)/data:/app/data:Z" \
        -e FLASK_ENV=production \
        -e SECRET_KEY="$(openssl rand -hex 32)" \
        -e DATABASE_URL="sqlite:///data/journalgrabber.db" \
        -e DOWNLOAD_PATH="/app/downloads" \
        -e ARXIV_API_DELAY="3.0" \
        -e DEFAULT_MAX_RESULTS="50" \
        -e DEFAULT_SEARCH_DAYS="7" \
        --restart unless-stopped \
        $IMAGE_NAME
    
    print_success "Container started successfully!"
    print_status "Application will be available at http://localhost:5000"
}

stop_container() {
    print_status "Stopping Journal Grabber container..."
    if $RUNTIME ps -q -f name=$CONTAINER_NAME | grep -q .; then
        $RUNTIME stop $CONTAINER_NAME
        print_success "Container stopped successfully!"
    else
        print_warning "Container is not running."
    fi
}

remove_container() {
    print_status "Removing Journal Grabber container..."
    if $RUNTIME ps -aq -f name=$CONTAINER_NAME | grep -q .; then
        $RUNTIME stop $CONTAINER_NAME 2>/dev/null || true
        $RUNTIME rm $CONTAINER_NAME
        print_success "Container removed successfully!"
    else
        print_warning "Container does not exist."
    fi
}

show_logs() {
    print_status "Showing container logs..."
    $RUNTIME logs -f $CONTAINER_NAME
}

show_status() {
    print_status "Container status:"
    if $RUNTIME ps -q -f name=$CONTAINER_NAME | grep -q .; then
        print_success "Container is running"
        $RUNTIME ps -f name=$CONTAINER_NAME
        echo
        print_status "Resource usage:"
        $RUNTIME stats --no-stream $CONTAINER_NAME
    else
        print_warning "Container is not running"
    fi
}

backup_data() {
    print_status "Creating backup of application data..."
    BACKUP_FILE="journalgrabber_backup_$(date +%Y%m%d_%H%M%S).tar.gz"
    tar -czf "$BACKUP_FILE" downloads/ data/ 2>/dev/null || {
        print_warning "Some directories don't exist yet, creating partial backup..."
        tar -czf "$BACKUP_FILE" --ignore-failed-read downloads/ data/ 2>/dev/null || true
    }
    print_success "Backup created: $BACKUP_FILE"
}

show_help() {
    echo "Journal Grabber - Container Management Script"
    echo
    echo "Usage: $0 [COMMAND]"
    echo
    echo "Commands:"
    echo "  build     Build the container image"
    echo "  start     Start the application container"
    echo "  stop      Stop the application container"
    echo "  restart   Restart the application container"
    echo "  remove    Remove the application container"
    echo "  logs      Show container logs"
    echo "  status    Show container status"
    echo "  backup    Backup application data"
    echo "  shell     Open shell in running container"
    echo "  update    Pull latest code and rebuild"
    echo "  help      Show this help message"
    echo
    echo "Examples:"
    echo "  $0 build && $0 start    # Build and start the application"
    echo "  $0 logs                 # View application logs"
    echo "  $0 backup               # Create data backup"
}

open_shell() {
    print_status "Opening shell in container..."
    if $RUNTIME ps -q -f name=$CONTAINER_NAME | grep -q .; then
        $RUNTIME exec -it $CONTAINER_NAME /bin/bash
    else
        print_error "Container is not running. Start it first with: $0 start"
        exit 1
    fi
}

update_application() {
    print_status "Updating application..."
    print_status "Pulling latest code..."
    git pull || print_warning "Git pull failed or not in a git repository"
    
    print_status "Rebuilding image..."
    build_image
    
    print_status "Restarting container..."
    remove_container
    start_container
    
    print_success "Application updated successfully!"
}

# Main script logic
detect_container_runtime

case "${1:-help}" in
    build)
        build_image
        ;;
    start)
        start_container
        ;;
    stop)
        stop_container
        ;;
    restart)
        stop_container
        start_container
        ;;
    remove)
        remove_container
        ;;
    logs)
        show_logs
        ;;
    status)
        show_status
        ;;
    backup)
        backup_data
        ;;
    shell)
        open_shell
        ;;
    update)
        update_application
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        echo
        show_help
        exit 1
        ;;
esac
