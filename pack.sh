rm -rf assignment4.tgz
rm -rf assignment4
mkdir assignment4
cp game_results.txt assignment4/game_results.txt
cp readme.txt assignment4/readme.txt
cp presubmission.log assignment4/presubmission.log
cp play.py assignment4/play.py
cp -r flat_mc_player/ assignment4/flat_mc_player/
cp -r gomoku4/ assignment4/gomoku4/
cp -r random_player/ assignment4/random_player/
tar cfz assignment4.tgz assignment4
rm -rf assignment4