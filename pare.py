#!/usr/bin/env python3
#############################################################################
# pare is a script to remove branches from a tree to maximize concordance/support
# of the underlying loci. This is the main interface.
#
# Gregg Thomas
# Fall 2021
#############################################################################

# pare.py -t full_coding_iqtree_astral.cf.rooted.tree -o test --overwrite -i 30

# PRUNING: Removing a branch from a tree
# PARING: Pruning one of the two descending clades from a branch to increase its length/support

#############################################################################

import sys
import os
import re
import lib.core as CORE
import lib.params as params
import lib.opt_parse as OP
import lib.tree as TREE

#############################################################################

if __name__ == '__main__':
# Main is necessary for multiprocessing to work on Windows.

    globs = params.init();
    # Get the global params as a dictionary.
    
    print("\n" + " ".join(sys.argv) + "\n");

    if any(v in sys.argv for v in ["--version", "-version", "--v", "-v"]):
        print("# pare version " + globs['interface-version'] + " released on " + globs['releasedate'])
        sys.exit(0);
    # The version option to simply print the version and exit.
    # Need to get actual PhyloAcc version for this, and not just the interface version.

    print("#");
    print("# " + "=" * 125);
    #print(CORE.welcome());
    if "-h" not in sys.argv:
        print("            Paring trees with heuristics\n");
    # A welcome banner.

    globs = OP.optParse(globs);
    # Getting the input parameters from optParse.

    if globs['info']:
        print("# --info SET. EXITING AFTER PRINTING PROGRAM INFO...\n#")
        sys.exit(0);
    if globs['norun']:
        print("# --norun SET. EXITING AFTER PRINTING OPTIONS INFO...\n#")
        sys.exit(0);
    # Early exit options

    ####################

    step_start_time = CORE.report_step(globs, "", "", "", start=True);
    # Initialize the step headers

    if globs['tree-input-type'] == "file":
        step = "Reading input file";
        step_start_time = CORE.report_step(globs, step, False, "In progress...");
        globs['orig-tree-str'] = open(globs['tree-input'], "r").read().strip();
        step_start_time = CORE.report_step(globs, step, step_start_time, "Success: file read");
    else:
        globs['orig-tree-str'] = globs['tree-input']
    # If the input type is a file, read the file here, otherwise take the string as the tree input

    ####################

    step = "Parsing input tree";
    step_start_time = CORE.report_step(globs, step, False, "In progress...");
    # Status update

    try:
        globs['tree-dict'], globs['labeled-tree-str'], globs['root'] = TREE.treeParse(globs['orig-tree-str']);
        #print(globs['labeled-tree-str']);
    except:
        print("\n\n");
        CORE.errorOut("1", "Error reading tree! Make sure it is formatted as a rooted, Newick tree.", globs);
    # Try and parse the tree with treeParse() and erorr out if fail

    globs['tips'] = [ n for n in globs['tree-dict'] if globs['tree-dict'][n][2] == 'tip' ];
    num_tips = len(globs['tips']);
    num_internals = len([ n for n in globs['tree-dict'] if globs['tree-dict'][n][2] == 'internal' ]);
    # Count the nodes

    step_start_time = CORE.report_step(globs, step, step_start_time, "Success: tree with " + str(num_tips) + " tips and " + str(num_internals) + " internal nodes read.");
    # Status update
    
    if globs['label-tree']:
        print("\n" + globs['labeled-tree-str'] +"\n");
        sys.exit(0);
    else:
        CORE.printWrite(globs['logfilename'], globs['log-v'], "# INFO: Original tree with node labels:\t" + globs['labeled-tree-str']);
    # Print the tree and exit if --labeltree is set

    ####################

    if globs['exempt-file']:
        step = "Reading exempt branches";
        step_start_time = CORE.report_step(globs, step, False, "In progress...", full_update=True);
        # Status update

        for line in open(globs['exempt-file']):
        # Every line in the file corresponds to one branch

            if line.startswith("#"):
                continue;
            # Skip lines that are commented out

            line = line.strip();
            # Remove trailing whitespace

            if " " in line:
            # If there is a space in the line, assume it is defining a branch with 2 tip labels

                specs = line.split(" ");
                # Split the line by the two tips

                if not all(s in globs['tips'] for s in specs):
                    globs['warnings'] += 1;
                    CORE.printWrite(globs['logfilename'], globs['log-v'], "# WARNING: Label in exempt file not found in tree. Skipping line: " + line);
                # Throw a warning if both of the tips aren't found in the tree and skip

                else:
                    exempt_node, mono_flag = TREE.LCA(specs, globs['tree-dict']);
                    # Get the least common ancestor of the given tips

                    CORE.printWrite(globs['logfilename'], globs['log-v'], "# INFO: " + line + " -> " + exempt_node);
                    # Info statement to show branch assignment

                    globs['exempt-branches'].append(exempt_node);
                    # Add the internal branch to the list of exempt branches

                    globs['exempt-clades'].append(set(TREE.getClade(exempt_node, globs['tree-dict'])));
                    # Get and add the full clade descending from the internal branch to the list of exempt clades
                # If both tips are found, get the full clade
            ## End tip block

            else:
            # If there is no space, assume it is defining an internal branch by label

                if line not in globs['tree-dict']:
                    globs['warnings'] += 1;
                    CORE.printWrite(globs['logfilename'], globs['log-v'], "# WARNING: Label in exempt file not found in tree. Skipping line: " + line);
                # Print a warning if the branch label isn't found in the tree

                else:
                    globs['exempt-branches'].append(line);
                    globs['exempt-clades'].append(set(TREE.getClade(line, globs['tree-dict'])));
                # Otherwise, add the branch and its clade to their global lists
            ## End label block
        ## End line/branch loop

        step_start_time = CORE.report_step(globs, step, step_start_time, "Success: " + str(len(globs['exempt-branches'])) + " branches will be exempt from paring.", full_update=True);
        # Status update
    ## Reading the file with branches exempt from pruning

    ####################

    pare = True;
    # Boolean for the paring loop

    iteration = 0;
    # Iteration counter

    cur_tree = globs['orig-tree-str'];
    # For the first iteration, the tree will be the input tree.

    while pare:
        iteration += 1;
        # Iterate the iteration counter

        ####################

        CORE.printWrite(globs['logfilename'], globs['log-v'], "# " + "-" * 50);
        step = "Paring iteration " + str(iteration);
        step_start_time = CORE.report_step(globs, step, False, "In progress...", full_update=True);
        # Status update

        globs, bl_threshold, pared_tree, pared_branches, pruned_tips, over_max_spec = TREE.pare(globs, cur_tree, iteration);
        # Call the paring algorithm for the current tree

        if over_max_spec:
            step_start_time = CORE.report_step(globs, step, step_start_time, "Truncated", full_update=True);
            # Status update      

            CORE.printWrite(globs['logfilename'], globs['log-v'], "# INFO: Branch length threshold for iteration:\t" + str(bl_threshold));
            CORE.printWrite(globs['logfilename'], globs['log-v'], "# INFO: This iteration would remove " + str(len(pruned_tips)) + " tips, which puts the total number pruned over the maximum limit (" + str(globs['max-spec']) +  "). Paring complete.");
            # Info update

            pare = False;

        elif len(pruned_tips) == 0:
            step_start_time = CORE.report_step(globs, step, step_start_time, "Success: No branches pared this iteration. Exiting.", full_update=True);
            # Status update              

            CORE.printWrite(globs['logfilename'], globs['log-v'], "# INFO: Branch length threshold for iteration:\t" + str(bl_threshold));
            # Info update

            pare = False;

        else: 
            step_start_time = CORE.report_step(globs, step, step_start_time, "Success: " + str(len(pruned_tips)) + " tips removed, " + str(len(pared_branches)) + " branches pared.", full_update=True);
            # Status update

            ####################

            CORE.printWrite(globs['logfilename'], globs['log-v'], "# INFO: Branch length threshold for iteration:\t" + str(bl_threshold));
            # Info update

            step = "Writing iteration " + str(iteration) + " files";
            step_start_time = CORE.report_step(globs, step, False, "In progress...");
            # Stats update

            with(open(os.path.join(globs['outdir'], "iter-" + str(iteration) + "-pruned-spec.txt"), "w")) as pruned_file:
                for tip in pruned_tips:
                    pruned_file.write(tip + "\n");
            # Write the species pruned in this iteration to a file

            with(open(os.path.join(globs['outdir'], "iter-" + str(iteration) + "-pared-branches.txt"), "w")) as pared_file:
                for n in pared_branches:
                    pared_file.write(n + "\n");
            # Write the branches pruned in this iteration to a file

            with(open(os.path.join(globs['outdir'], "iter-" + str(iteration) + "-pared.tre"), "w")) as pared_tree_file:
                pared_tree_file.write(pared_tree);
            # Write the pared tree from this iteration to a file  

            step_start_time = CORE.report_step(globs, step, step_start_time, "Success");
            # Status update

            ####################

            cur_tree = pared_tree;
            # Set the tree for the next iteration to be the pared tree from this iteration

            globs['bl-thresholds'].append(bl_threshold);
            globs['pared-branches'].append(pared_branches);
            globs['total-pared-branches'] += len(pared_branches);
            globs['pruned-tips'].append(pruned_tips);
            globs['total-pruned-tips'] += len(pruned_tips);
            globs['iter-trees'].append(pared_tree);
            # Add the pared branches and pruned tips from this iteration to the global lists for all iterations

            if iteration == globs['max-iterations']:
                iteration += 1;
                pare = False;
            # Check for stopping conditions to set pare to False
    # The paring loop

    ####################

    CORE.printWrite(globs['logfilename'], globs['log-v'], "# " + "-" * 50);
    step = "Writing summary stats to log";
    step_start_time = CORE.report_step(globs, step, False, "In progress...");
    # Status update    

    headers = ["iteration", "branch length threshold", "branches pared", "tips pruned", "tree"];
    CORE.printWrite(globs['logfilename'], 3, "\t".join(headers));
    for i in range(iteration):
        
        iter_tree = globs['iter-trees'][i] + ";";
        
        #iter_tree = re.sub("<[\d]+>_", "", globs['iter-trees'][i]);
        #iter_tree = re.sub("<[\d]+>", "", iter_tree) + ";";
        # Removes the internal node labels from the tree

        if i == 0:
            outline = [ "0", "NA", "NA", "NA", iter_tree ];
        else:
            iter_str = str(i);
            outline = [ iter_str, str(globs['bl-thresholds'][i-1]), str(len(globs['pared-branches'][i-1])), str(len(globs['pruned-tips'][i-1])), iter_tree ];
        CORE.printWrite(globs['logfilename'], 3, "\t".join(outline));

    tips_file = os.path.join(globs['outdir'], "all-pruned-tips.txt");
    with open(tips_file, "w") as tipsfile:
        for iter_tips in globs['pruned-tips']:
            for tip in iter_tips:
                tipsfile.write(tip + "\n");

    step_start_time = CORE.report_step(globs, step, step_start_time, "Success");
    # Status update

    ####################

    final_msg = "# Pared " + str(globs['total-pared-branches']) + " total branches and removed " + str(globs['total-pruned-tips']) + " total tips.";
    CORE.endProg(globs, final_msg);
    # A nice way to end the program

#############################################################################

