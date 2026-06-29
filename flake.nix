{
  description = "ha-green-button development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    flake-parts = {
      url = "github:hercules-ci/flake-parts";
      inputs.nixpkgs-lib.follows = "nixpkgs";
    };
    git-hooks-nix = {
      url = "github:cachix/git-hooks.nix";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.flake-compat.follows = "";
    };
  };

  outputs =
    inputs@{ flake-parts, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      imports = [ inputs.git-hooks-nix.flakeModule ];
      systems = [ "x86_64-linux" ];

      perSystem =
        { config, pkgs, ... }:
        {
          pre-commit.settings = {
            hooks = {
              end-of-file-fixer.enable = true;
              trim-trailing-whitespace.enable = true;
              check-yaml.enable = true;
              check-json.enable = true;
              check-added-large-files.enable = true;
              prettier.enable = true;
              ruff-format.enable = true;
              ruff = {
                enable = true;
              };
            };
          };

          devShells.default = pkgs.mkShell {
            inputsFrom = [ config.pre-commit.devShell ];
            packages = with pkgs; [
              python314
              uv
            ];
          };
        };
    };
}
