{
  description = "Development environment for ea-handbook";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      supportedSystems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forEachSupportedSystem = f: nixpkgs.lib.genAttrs supportedSystems (system: f {
        pkgs = import nixpkgs { inherit system; };
      });
    in
    {
      devShells = forEachSupportedSystem ({ pkgs }: {
        default = pkgs.mkShell {
          buildInputs = with pkgs; [
            uv
          ];

          shellHook = ''
            echo "Setting up Python 3.14 using uv..."
            uv python install 3.14
            echo "Run 'uv sync' or 'uv venv' to set up the virtual environment."
          '';
        };
      });
    };
}
