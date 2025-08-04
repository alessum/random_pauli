using Pkg
Pkg.activate(".")

using Random
using JSON

# Parameters
num_trials = 1000
N = 6
seed = 1234
filename = "random_archive/angles_N$(N).json"
# Angle keys
angle_keys = ["θ1", "θ2", "Jx", "Jz", "θ3", "θ4"]

if isfile(filename)
    println("File $filename already exists — skipping save.")
else
    # Seed the RNG
    rng = MersenneTwister(seed)

    # Construct the nested structure
    data = [ [ Dict(k => rand(rng)*2π - π for k in angle_keys)
                for gate in 1:N ]
            for trial in 1:num_trials ]

    # Save to JSON file
    open(filename, "w") do io
        JSON.print(io, data)  # no indent argument!
    end

    println("Data saved to $filename")
end